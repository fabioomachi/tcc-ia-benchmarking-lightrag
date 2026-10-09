"""Suporte compartilhado à parada graciosa por cota esgotada (HTTP 429).

Usado pelos lotes longos (`index`, `run`, `run-direct`, `run-clarify`): ao
detectar `QuotaExhaustedError`, o comando interrompe o lote, persiste o
progresso e orienta a retomada posterior com o comando literal.
"""

import json
from pathlib import Path

from rich.console import Console

from ragbench.core.models import QueryExecutionRecord
from ragbench.reporting.reporters import BenchmarkReporter

QUOTA_EXIT_CODE = 3
"""Exit code distinto para cota da API esgotada (permite automação/cron detectar)."""


def export_run_reports(
    records: list[QueryExecutionRecord], run_dir: Path, results_dir: Path
) -> tuple[Path, Path]:
    """Exporta CSV + relatório MD do lote (completo ou parcial)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = run_dir / "benchmark_analise_detalhada.csv"
    md_path = run_dir / "resumo_benchmark.md"
    BenchmarkReporter.export_execution_csv(records, csv_path)
    BenchmarkReporter.generate_execution_markdown_report(records, md_path)
    BenchmarkReporter.export_execution_csv(records, results_dir / "benchmark_analise_detalhada.csv")
    BenchmarkReporter.generate_execution_markdown_report(
        records, results_dir / "resumo_benchmark.md"
    )
    return csv_path, md_path


def merge_run_manifest(manifest: list[dict], manifest_path: Path) -> list[dict]:
    """Mescla entries novas com o manifest de invocação anterior (puro).

    Índices pulados via checkpoint não passam pelo loop do lote; sem merge,
    manifest/golden de runs retomadas sairiam parciais e o `eval` avaliaria
    só o subconjunto. Entradas novas prevalecem; arquivo ausente ou
    ilegível mantém só as novas.
    """
    if not manifest_path.exists():
        return manifest
    try:
        prior = json.loads(manifest_path.read_text(encoding="utf-8"))
        merged = {m["index"]: m for m in prior if isinstance(m, dict)}
        merged.update({m["index"]: m for m in manifest})
        return [merged[k] for k in sorted(merged)]
    except (json.JSONDecodeError, OSError, KeyError):
        return manifest


def print_quota_stopped(
    console: Console, *, resume_cmd: str, remaining: int, checkpoint: Path
) -> None:
    """Imprime a mensagem padrão de interrupção por quota com guia de retomada."""
    console.print(
        f"[bold yellow]⏸ Execução interrompida: cota da API esgotada. "
        f"{remaining} item(ns) pendente(s).[/bold yellow]"
    )
    console.print(f"📁 Checkpoint preservado em: [cyan]{checkpoint}[/cyan]")
    console.print(f"▶ Retome após a renovação da cota com: [cyan]{resume_cmd}[/cyan]")
    console.print(
        "[dim]Regras da retomada: mesmo --run-name, mesmos parâmetros, sem --no-resume.[/dim]"
    )
