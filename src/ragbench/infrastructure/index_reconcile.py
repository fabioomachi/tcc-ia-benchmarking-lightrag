"""Reconciliação do manifesto anti-duplicata com um grafo LightRAG pré-existente.

Uso: bases indexadas antes da introdução de `index_manifest.json` não são
reconhecidas pelo modo incremental — sem reconcile, o próximo `index`
reinseriria tudo como duplicata. O reconcile lê `kv_store_doc_status.json` +
`kv_store_full_docs.json`, casa cada doc `processed` com o arquivo em
`pops_dir` via prefixo `DOCUMENTO_ORIGEM: <nome>` e, se o conteúdo em disco for
idêntico ao guardado no grafo, registra o SHA256 no manifesto.

Regras (aprovadas):
- Arquivo alterado em disco → NÃO registra, entra em `altered` (próximo
  `index` cai no aviso "alterado, use --clean").
- Arquivo ausente em disco → `missing_on_disk`, não registra.
- `dry_run=True` → só relata, não escreve nada.
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from ragbench.core.models import IndexedDocument, ReconcileReport
from ragbench.infrastructure.index_manifest import (
    compute_sha256,
    load_manifest,
    manifest_path,
    save_manifest_atomic,
)
from ragbench.infrastructure.logging import get_logger

logger = get_logger("ragbench.index_reconcile")

DOC_STATUS_FILENAME = "kv_store_doc_status.json"
FULL_DOCS_FILENAME = "kv_store_full_docs.json"

_DOC_ORIGIN_RE = re.compile(r"^DOCUMENTO_ORIGEM:\s*(.+?)\s*\n", re.MULTILINE)


def strip_origin_prefix(content: str) -> tuple[str | None, str]:
    """Separa `DOCUMENTO_ORIGEM: <nome>` do corpo. Retorna (nome|None, corpo)."""
    match = _DOC_ORIGIN_RE.search(content)
    if not match:
        return None, content
    return match.group(1).strip(), content[match.end() :].lstrip("\n")


def extract_indexed_docs(
    doc_status: dict[str, dict], full_docs: dict[str, dict]
) -> tuple[list[tuple[str, str]], int]:
    """Extrai (filename, stored_raw) dos docs com `status == processed`.

    Retorna (lista, ignored_non_processed). Docs sem prefixo reconhecível são
    ignorados (contados como ignored).
    """
    indexed: list[tuple[str, str]] = []
    ignored = 0
    for doc_id, entry in doc_status.items():
        if not isinstance(entry, dict) or entry.get("status") != "processed":
            ignored += 1
            continue
        filename: str | None = None
        stored_raw = ""
        summary = entry.get("content_summary") or ""
        filename, _ = strip_origin_prefix(str(summary))
        full = full_docs.get(doc_id)
        if isinstance(full, dict) and isinstance(full.get("content"), str):
            f_name, f_raw = strip_origin_prefix(full["content"])
            filename = filename or f_name
            stored_raw = f_raw
        if not filename:
            ignored += 1
            continue
        indexed.append((filename, stored_raw))
    return indexed, ignored


def _read_json_tolerant(path: Path) -> dict:
    """Lê JSON; ausente/corrompido resulta em {} com warning."""
    if not path.exists():
        logger.warning("Arquivo de grafo ausente: %s", path)
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("Arquivo de grafo corrompido em %s (%s); ignorando.", path, e)
        return {}


def reconcile_manifest(storage_dir: Path, pops_dir: Path, dry_run: bool = False) -> ReconcileReport:
    """Reconstrói o manifesto a partir do grafo existente (sem LLM)."""
    doc_status = _read_json_tolerant(storage_dir / DOC_STATUS_FILENAME)
    full_docs = _read_json_tolerant(storage_dir / FULL_DOCS_FILENAME)
    indexed, ignored = extract_indexed_docs(doc_status, full_docs)

    manifest = load_manifest(manifest_path(storage_dir))
    report = ReconcileReport(ignored_non_processed=ignored)

    for filename, stored_raw in indexed:
        disk_path = pops_dir / filename
        if not disk_path.exists():
            report.missing_on_disk.append(filename)
            continue
        try:
            disk_text = disk_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Não foi possível ler %s (%s); tratando como alterado.", disk_path, e)
            report.altered.append(filename)
            continue
        # Tolerância a newline final de arquivo: o LightRAG normaliza o
        # trailing newline ao armazenar, mas o hash do manifesto é sempre do
        # arquivo em disco (o que o `index` incremental recalcula).
        if disk_text.rstrip("\r\n") != stored_raw.rstrip("\r\n"):
            report.altered.append(filename)
            continue
        sha, num_bytes = compute_sha256(disk_path)
        manifest.upsert(IndexedDocument(filename=filename, sha256=sha, num_bytes=num_bytes))
        report.reconciled.append(filename)

    if dry_run or not report.reconciled:
        report.manifest_written = False
        return report

    manifest_file = manifest_path(storage_dir)
    if manifest_file.exists():
        backup = manifest_file.with_name(
            f"{manifest_file.name}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        shutil.copy2(manifest_file, backup)
        logger.info("Backup do manifesto anterior em %s", backup)
    save_manifest_atomic(manifest, manifest_file)
    report.manifest_written = True
    return report
