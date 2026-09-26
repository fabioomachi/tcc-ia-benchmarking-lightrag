"""Comando `run`: bateria de benchmark em lote com checkpointing."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from ragbench.cli_commands import deps
from ragbench.cli_commands.quota_support import (
    QUOTA_EXIT_CODE,
    export_run_reports,
    print_quota_stopped,
)
from ragbench.core.exceptions import QuotaExhaustedError
from ragbench.core.models import SearchMode
from ragbench.engines.lightrag_engine import LightRAGEngine
from ragbench.infrastructure.logging import setup_logging
from ragbench.infrastructure.storage import SQLiteExecutionStorage
from ragbench.runner import BenchmarkRunner


def build_run_id(run_name: str | None, mode: str, now: datetime) -> str:
    """Compõe o identificador da run (puro: sem I/O)."""
    return run_name or f"run_{now.strftime('%Y%m%d_%H%M%S')}_{mode}"


def run_benchmark(
    target: Annotated[Path | None, typer.Option(help="Arquivo ou pasta de perguntas")] = None,
    mode: Annotated[
        str, typer.Option(help="Modo de busca (naive, local, global, hybrid)")
    ] = "hybrid",
    top_k: Annotated[int, typer.Option(help="Top-K entidades e chunks recuperados")] = 5,
    concurrency: Annotated[int, typer.Option(help="Requisições concorrentes ao Ollama")] = 10,
    resume: Annotated[bool, typer.Option(help="Retoma de checkpoint anterior")] = True,
    run_name: Annotated[str | None, typer.Option(help="Nome identificador da execução")] = None,
) -> None:
    """Executa a bateria de testes de benchmark em lote com checkpointing e relatórios automáticos.

    Sai com código 3 (QUOTA_EXIT_CODE) se a cota da API for esgotada: o lote é
    interrompido, o progresso é exportado parcialmente e a retomada posterior
    (mesmo --run-name) continua de onde parou.
    """
    settings = deps.get_settings()
    target_path = target or settings.questions_dir
    search_mode = SearchMode(mode)

    run_id = build_run_id(run_name, mode, datetime.now())
    setup_logging(settings, run_id=run_id)
    run_dir = settings.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    db_path = run_dir / "checkpoint.sqlite3"
    storage = SQLiteExecutionStorage(db_path)

    async def _run():
        queries = BenchmarkRunner.load_queries_from_path(target_path)
        if not queries:
            deps.console.print(f"[yellow]Nenhuma pergunta encontrada em {target_path}[/yellow]")
            return

        engine = LightRAGEngine.for_chat(settings=settings)
        await engine.initialize()

        runner = BenchmarkRunner(engine=engine, storage=storage, settings=settings)
        deps.console.print(
            f"[bold blue]Disparando benchmark: {len(queries)} perguntas | Modo: {mode} | Concorrência: {concurrency}[/bold blue]"
        )

        try:
            records = await runner.execute_batch(
                queries=queries,
                mode=search_mode,
                top_k=top_k,
                concurrency=concurrency,
                resume=resume,
            )
        except QuotaExhaustedError as e:
            try:
                await engine.finalize()
            except Exception as fe:
                deps.console.print(f"[yellow]⚠ Falha ao persistir storages: {fe}[/yellow]")
            records = await asyncio.to_thread(storage.load_all_records)
            await asyncio.to_thread(export_run_reports, records, run_dir, settings.results_dir)
            completed = await asyncio.to_thread(storage.get_completed_indices)
            target_opt = f" --target {target_path}" if target else ""
            print_quota_stopped(
                deps.console,
                resume_cmd=(
                    f"uv run ragbench run --run-name {run_id} "
                    f"--mode {mode} --top-k {top_k}{target_opt}"
                ),
                remaining=len(queries) - len(completed),
                checkpoint=db_path,
            )
            raise typer.Exit(code=QUOTA_EXIT_CODE) from e

        await engine.finalize()

        # Exportações automáticas (I/O de disco fora do loop)
        csv_path, md_path = await asyncio.to_thread(
            export_run_reports, records, run_dir, settings.results_dir
        )

        deps.console.print("\n[bold green]✅ Execução finalizada![/bold green]")
        deps.console.print(f"📁 Checkpoint SQLite: [cyan]{db_path}[/cyan]")
        deps.console.print(f"📊 Relatório Markdown: [cyan]{md_path}[/cyan]")
        deps.console.print(f"📑 Exportação CSV: [cyan]{csv_path}[/cyan]")
        deps.console.print(f"📝 Log: [cyan]{settings.logging.dir / f'{run_id}.log'}[/cyan]")

    asyncio.run(_run())
