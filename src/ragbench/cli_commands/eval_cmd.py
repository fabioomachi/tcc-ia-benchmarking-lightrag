"""Comando `eval`: avaliação RAGAS sobre um checkpoint anterior."""

import sys
from pathlib import Path
from typing import Annotated

import typer

from ragbench.cli_commands import deps
from ragbench.cli_commands.quota_support import QUOTA_EXIT_CODE, print_quota_stopped
from ragbench.core.exceptions import QuotaExhaustedError
from ragbench.evaluation.ragas_evaluator import RagasEvaluator
from ragbench.infrastructure.storage import SQLiteExecutionStorage
from ragbench.reporting.reporters import BenchmarkReporter


def resolve_eval_db_path(runs_dir: Path, run_id: str | None, checkpoint: Path | None) -> Path:
    """Resolve o checkpoint a avaliar (puro: sem console, sem saída).

    Levanta FileNotFoundError quando não há checkpoint disponível.
    """
    if checkpoint:
        return checkpoint
    if run_id:
        return runs_dir / run_id / "checkpoint.sqlite3"
    # Pega a run mais recente
    runs = sorted(
        list(runs_dir.glob("*/checkpoint.sqlite3")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not runs:
        raise FileNotFoundError("Nenhum checkpoint de benchmark encontrado para avaliar.")
    return runs[0]


def evaluate_run(
    run_id: Annotated[str | None, typer.Option(help="ID da run a avaliar")] = None,
    checkpoint: Annotated[Path | None, typer.Option(help="Caminho do checkpoint.sqlite3")] = None,
    golden: Annotated[Path | None, typer.Option(help="Golden dataset específico")] = None,
) -> None:
    """Executa a avaliação de qualidade LLM-as-a-Judge (RAGAS) em uma execução anterior.

    Sai com código 3 (QUOTA_EXIT_CODE) se a cota da API for esgotada: nenhum
    arquivo de resultado é sobrescrito e a reexecução posterior (mesmo comando)
    refaz a avaliação por inteiro.
    """
    settings = deps.get_settings()
    try:
        db_path = resolve_eval_db_path(settings.runs_dir, run_id, checkpoint)
    except FileNotFoundError:
        deps.console.print("[red]Nenhum checkpoint de benchmark encontrado para avaliar.[/red]")
        sys.exit(1)
        raise  # inalcançável; apenas para o tipo

    deps.console.print(f"[bold blue]Avaliando execuções de: {db_path}[/bold blue]")
    storage = SQLiteExecutionStorage(db_path)
    records = storage.load_all_records()

    golden_path = golden
    if golden_path is None:
        # run-clarify gera golden.json próprio (queries enriquecidas); usa ele
        # automaticamente quando existir, senão cai no golden padrão.
        run_golden = db_path.parent / "golden.json"
        if run_golden.exists():
            golden_path = run_golden
            deps.console.print(f"[dim]Usando golden da run: {golden_path}[/dim]")

    evaluator = RagasEvaluator(settings=settings)
    if checkpoint:
        retry_cmd = f"uv run ragbench eval --checkpoint {checkpoint}"
    elif run_id:
        retry_cmd = f"uv run ragbench eval --run-id {run_id}"
    else:
        retry_cmd = "uv run ragbench eval"
    if golden:
        retry_cmd += f" --golden {golden}"
    try:
        if not evaluator.probe_quota():
            raise QuotaExhaustedError("Sonda pré-voo indicou cota indisponível.")
        df_results = evaluator.run_evaluation(records, golden_path=golden_path)
    except QuotaExhaustedError as e:
        # Preserva CSV/MD bons anteriores: nada é sobrescrito aqui.
        print_quota_stopped(
            deps.console,
            resume_cmd=retry_cmd,
            remaining=len(records),
            checkpoint=db_path,
        )
        deps.console.print(f"[dim]Detalhe: {e}[/dim]")
        raise typer.Exit(code=QUOTA_EXIT_CODE) from e

    out_csv = db_path.parent / "ragas_evaluation_results.csv"
    out_md = db_path.parent / "resumo_qualidade_ragas.md"
    df_results.to_csv(out_csv, index=False, encoding="utf-8-sig")
    BenchmarkReporter.generate_ragas_markdown_report(df_results, out_md)

    # Copia para pasta legada resultados/
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    df_results.to_csv(
        settings.results_dir / "ragas_evaluation_results.csv", index=False, encoding="utf-8-sig"
    )
    BenchmarkReporter.generate_ragas_markdown_report(
        df_results, settings.results_dir / "resumo_qualidade_ragas.md"
    )

    deps.console.print("[bold green]✅ Avaliação RAGAS concluída![/bold green]")
    deps.console.print(f"📊 Relatório de Qualidade: [cyan]{out_md}[/cyan]")
    deps.console.print(f"📑 Tabela CSV: [cyan]{out_csv}[/cyan]")
