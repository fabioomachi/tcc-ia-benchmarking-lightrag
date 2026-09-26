"""Manifesto de indexação: controle anti-duplicata por SHA256 do conteúdo.

O arquivo vive dentro de `settings.storage_dir` (`index_manifest.json`), de modo
que `--clean` (que remove o diretório) o apaga automaticamente. Leitura de
manifesto ausente/corrompido retorna um manifesto vazio com aviso — nunca quebra
a indexação. Escrita é atômica (tmp + replace).
"""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from ragbench.core.models import IndexManifest
from ragbench.infrastructure.logging import get_logger

logger = get_logger("ragbench.index_manifest")

MANIFEST_FILENAME = "index_manifest.json"


def manifest_path(storage_dir: Path) -> Path:
    """Caminho do manifesto dentro do diretório de armazenamento."""
    return storage_dir / MANIFEST_FILENAME


def compute_sha256(path: Path) -> tuple[str, int]:
    """Calcula SHA256 do conteúdo bruto do arquivo. Retorna (hex, num_bytes)."""
    digest = hashlib.sha256()
    num_bytes = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
            num_bytes += len(chunk)
    return digest.hexdigest(), num_bytes


def load_manifest(path: Path) -> IndexManifest:
    """Carrega o manifesto; ausente/corrompido resulta em manifesto vazio."""
    if not path.exists():
        return IndexManifest()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return IndexManifest.model_validate(data)
    except Exception as e:
        logger.warning("Manifesto de indexação corrompido em %s (%s); reindexando.", path, e)
        return IndexManifest()


def save_manifest_atomic(manifest: IndexManifest, path: Path) -> None:
    """Persiste o manifesto de forma atômica (tmp no mesmo dir + replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = manifest.model_dump_json(indent=2, ensure_ascii=False)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".manifest_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
