"""Comando `index`: indexação de POPs no grafo LightRAG."""

import asyncio
import shutil
from itertools import chain
from pathlib import Path
from typing import Annotated

import typer

from ragbench.cli_commands import deps
from ragbench.cli_commands.quota_support import QUOTA_EXIT_CODE
from ragbench.core.exceptions import QuotaExhaustedError
from ragbench.core.models import IndexedDocument, IndexManifest
from ragbench.engines.lightrag_engine import LightRAGEngine
from ragbench.infrastructure.index_manifest import (
    compute_sha256,
    load_manifest,
    manifest_path,
    save_manifest_atomic,
)

POP_PIX_CONTENT = (
    "PROCEDIMENTO OPERACIONAL PADRÃO - POP-014: Cancelamento de PIX por Suspeita de Fraude.\n"
    "1. O operador deve validar a identidade do cliente via biometria facial no sistema BioCheck.\n"
    "2. Caso haja contestação por golpe do falso leilão, o bloqueio cautelar deve ser acionado no sistema MED (Mecanismo Especial de Devolução) do BACEN em até 30 minutos corridos após a denúncia.\n"
    "3. EXCEÇÃO: É estritamente proibido o estorno manual sem a autorização prévia, registrada em ticket, da mesa de compliance antifraude.\n"
    "4. Falhas na aplicação do bloqueio cautelar no prazo regulatório geram passivo ao banco de acordo com a resolução BCB nº 103."
)

POP_CARTAO_CONTENT = (
    "PROCEDIMENTO OPERACIONAL PADRÃO - POP-015: Bloqueio de Cartão de Crédito por Suspeita de Fraude.\n"
    "1. O operador deve verificar o padrão de compras no sistema de monitoramento transacional.\n"
    "2. Em caso de transações internacionais atípicas consecutivas, acionar o bloqueio preventivo do cartão.\n"
    "3. CONDICAO: O bloqueio preventivo exige a comunicação imediata ao cliente via SMS e e-mail cadastrado, conforme determina a norma do BACEN sobre transparência.\n"
    "4. O desbloqueio só pode ser realizado após contato ativo do cliente validado pelo sistema BioCheck."
)


def discover_pop_files(target_dir: Path) -> list[Path]:
    """Lista POPs (.txt/.md) do diretório (puro: sem escrita)."""
    return list(chain(target_dir.glob("*.txt"), target_dir.glob("*.md")))


def seed_default_pops(target_dir: Path) -> list[Path]:
    """Cria os POPs sintéticos padrão e retorna os arquivos descobertos."""
    (target_dir / "pop_cancelamento_pix.txt").write_text(POP_PIX_CONTENT, encoding="utf-8")
    (target_dir / "pop_bloqueio_cartao.txt").write_text(POP_CARTAO_CONTENT, encoding="utf-8")
    return discover_pop_files(target_dir)


def index_documents(
    pops_dir: Annotated[Path | None, typer.Option(help="Diretório com arquivos POPs .txt")] = None,
    clean: Annotated[
        bool, typer.Option(help="Limpa o banco de grafos antes de indexar (padrão: incremental)")
    ] = False,
    force: Annotated[
        bool,
        typer.Option(help="Reinsere mesmo se o manifesto disser que já foi indexado"),
    ] = False,
    reconcile: Annotated[
        bool,
        typer.Option(
            help="Reconstrói index_manifest.json a partir do grafo existente, sem indexar"
        ),
    ] = False,
    dry_run: Annotated[
        bool, typer.Option(help="Com --reconcile: só relata, sem escrever o manifesto")
    ] = False,
) -> None:
    """Indexa documentos POP no banco de grafos e vetores do LightRAG.

    Sai com código 3 (QUOTA_EXIT_CODE) se a cota da API for esgotada: o lote é
    interrompido, o resíduo parcial do documento corrente é removido e a
    retomada posterior reinsere do zero o que ficou pendente.
    """
    settings = deps.get_settings()
    target_dir = pops_dir or settings.pops_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    storage_dir = settings.storage_dir

    if reconcile:
        if clean or force:
            deps.console.print("[red]--reconcile é incompatível com --clean/--force.[/red]")
            raise typer.Exit(code=2)
        from ragbench.infrastructure.index_reconcile import reconcile_manifest

        report = reconcile_manifest(storage_dir, target_dir, dry_run=dry_run)
        for name in report.reconciled:
            deps.console.print(f"  [green]✔ {name} reconciliado.[/green]")
        for name in report.altered:
            deps.console.print(
                f"  [yellow]⚠ {name} alterado desde a indexação; "
                "não registrado (use --clean para atualizar).[/yellow]"
            )
        for name in report.missing_on_disk:
            deps.console.print(f"  [red]✖ {name} está no grafo mas ausente em disco.[/red]")
        if dry_run:
            deps.console.print("[blue]dry-run: manifesto não foi escrito.[/blue]")
        elif report.manifest_written:
            deps.console.print(
                f"[bold green]✅ Manifesto reconciliado "
                f"({len(report.reconciled)} documentos).[/bold green]"
            )
        else:
            deps.console.print("[yellow]Nada a reconciliar; manifesto inalterado.[/yellow]")
        return

    if clean and storage_dir.exists():
        deps.console.print("[yellow]Higienizando banco de grafos anterior...[/yellow]")
        shutil.rmtree(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)

    txt_files = discover_pop_files(target_dir)

    if not txt_files:
        deps.console.print(
            "[yellow]Nenhum arquivo encontrado. Criando POPs sintéticos padrão...[/yellow]"
        )
        txt_files = seed_default_pops(target_dir)

    manifest_file = manifest_path(storage_dir)
    if clean or force:
        manifest = IndexManifest()
    else:
        manifest = load_manifest(manifest_file)
    known_hashes = set() if force else manifest.known_hashes()
    known_filenames = set() if force else manifest.known_filenames()

    deps.console.print(
        f"[bold blue]Iniciando indexação de {len(txt_files)} documentos...[/bold blue]"
    )

    async def _run_index():
        pending: list[tuple[Path, str, int]] = []
        for doc in txt_files:
            sha, num_bytes = await asyncio.to_thread(compute_sha256, doc)
            if sha in known_hashes:
                deps.console.print(
                    f" -> [yellow]⏭ {doc.name} já indexado (sha={sha[:12]}…). Pulando.[/yellow]"
                )
                continue
            if doc.name in known_filenames:
                deps.console.print(
                    f" -> [yellow]⚠ {doc.name} alterado desde a indexação "
                    f"(sha={sha[:12]}…). Pulando; use --clean para atualizar.[/yellow]"
                )
                continue
            pending.append((doc, sha, num_bytes))

        if not pending:
            deps.console.print(
                "[green]Nada a indexar: todos os documentos já estão no grafo.[/green]"
            )
            return

        engine = LightRAGEngine.for_index(settings=settings)
        await engine.initialize()

        async def _cleanup_partial(doc_name: str) -> bool:
            """Remove resíduo parcial do documento (best-effort, com relato)."""
            cleaned = await engine.adelete_doc_by_filename(doc_name)
            if cleaned:
                deps.console.print(f"    [green]✔ Resíduo parcial de {doc_name} removido.[/green]")
            else:
                deps.console.print(
                    f"    [yellow]⚠ Limpeza incompleta de {doc_name}; "
                    "será reprocessado na próxima execução.[/yellow]"
                )
            return cleaned

        for idx, (doc, sha, num_bytes) in enumerate(pending):
            deps.console.print(f" -> Indexando: [cyan]{doc.name}[/cyan] ...")
            raw_text = await asyncio.to_thread(doc.read_text, encoding="utf-8")
            enriched = f"DOCUMENTO_ORIGEM: {doc.name}\n\n{raw_text}"
            try:
                await engine.ainsert(enriched)
                # O LightRAG pode marcar FAILED sem lançar: só registra no
                # manifesto o que está comprovadamente processado.
                status = await engine.get_doc_status_by_filename(doc.name)
                if status != "processed":
                    deps.console.print(
                        f"    [red]✖ {doc.name} terminou com status '{status}' "
                        "(falha silenciosa do pipeline).[/red]"
                    )
                    await _cleanup_partial(doc.name)
                    continue
                manifest.upsert(IndexedDocument(filename=doc.name, sha256=sha, num_bytes=num_bytes))
                await asyncio.to_thread(save_manifest_atomic, manifest, manifest_file)
                deps.console.print(f"    [green]✔ {doc.name} inserido no grafo.[/green]")
            except QuotaExhaustedError as e:
                deps.console.print(f"    [red]🛑 Cota da API esgotada em {doc.name}: {e}[/red]")
                await _cleanup_partial(doc.name)
                try:
                    await engine.finalize()
                except Exception as fe:
                    deps.console.print(f"    [yellow]⚠ Falha ao persistir storages: {fe}[/yellow]")
                remaining = len(pending) - idx
                deps.console.print(
                    f"[bold yellow]⏸ Indexação interrompida: {remaining} documento(s) pendente(s). "
                    "Rode `ragbench index` novamente após a renovação da cota.[/bold yellow]"
                )
                raise typer.Exit(code=QUOTA_EXIT_CODE) from e
            except Exception as e:
                deps.console.print(f"    [red]✖ Falha em {doc.name}: {e}[/red]")
                await _cleanup_partial(doc.name)

        await engine.finalize()

    asyncio.run(_run_index())
    deps.console.print("[bold green]✅ Indexação de documentos concluída com sucesso![/bold green]")
