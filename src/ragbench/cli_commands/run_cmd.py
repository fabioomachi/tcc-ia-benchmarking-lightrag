"""Comando `run`: bateria de benchmark em lote com checkpointing."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from ragbench.cli_commands import deps
from ragbench.core.models import SearchMode
from ragbench.engines.lightrag_engine import LightRAGEngine
from ragbench.infrastructure.logging import setup_logging
from ragbench.infrastructure.storage import SQLiteExecutionStorage
from ragbench.reporting.reporters import BenchmarkReporter
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
    """Executa a bateria de testes de benchmark em lote com checkpointing e relatórios automáticos."""
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

        records = await runner.execute_batch(
            queries=queries,
            mode=search_mode,
            top_k=top_k,
            concurrency=concurrency,
            resume=resume,
        )

        await engine.finalize()

        # Exportações automáticas (I/O de disco fora do loop)
        csv_path = run_dir / "benchmark_analise_detalhada.csv"
        md_path = run_dir / "resumo_benchmark.md"
        await asyncio.to_thread(BenchmarkReporter.export_execution_csv, records, csv_path)
        await asyncio.to_thread(
            BenchmarkReporter.generate_execution_markdown_report, records, md_path
        )

        # Cópia para o diretório legado de resultados para compatibilidade
        target_results_dir = settings.results_dir
        target_results_dir.mkdir(parents=True, exist_ok=True)

        await asyncio.to_thread(
            BenchmarkReporter.export_execution_csv,
            records,
            target_results_dir / "benchmark_analise_detalhada.csv",
        )
        await asyncio.to_thread(
            BenchmarkReporter.generate_execution_markdown_report,
            records,
            target_results_dir / "resumo_benchmark.md",
        )

        deps.console.print("\n[bold green]✅ Execução finalizada![/bold green]")
        deps.console.print(f"📁 Checkpoint SQLite: [cyan]{db_path}[/cyan]")
        deps.console.print(f"📊 Relatório Markdown: [cyan]{md_path}[/cyan]")
        deps.console.print(f"📑 Exportação CSV: [cyan]{csv_path}[/cyan]")
        deps.console.print(f"📝 Log: [cyan]{settings.logging.dir / f'{run_id}.log'}[/cyan]")

    asyncio.run(_run())
