"""Comando `run-direct`: baseline LLM puro (sem grafo) nos 24 cenários.

Duas variantes de input (`--input completa|incompleta`), mesmos artefatos
do `run` (checkpoint + CSV + MD + `golden.json` próprio), records com
`mode=direct` + `source=baseline_engine`, cache semântico desligado para
zero contaminação entre braços. Avaliável com `eval --run-id`.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from ragbench.cli_commands import deps
from ragbench.cli_commands.run_cmd import build_run_id
from ragbench.conversational.batch import load_scenarios
from ragbench.core.models import (
    QueryExecutionRecord,
    QueryInteractionSource,
    RagExecutionStatus,
    SearchMode,
)
from ragbench.engines.direct_llm_engine import DirectLLMEngine
from ragbench.infrastructure.logging import setup_logging
from ragbench.infrastructure.storage import SQLiteExecutionStorage
from ragbench.reporting.reporters import BenchmarkReporter


def run_direct_batch(
    scenarios: Annotated[Path | None, typer.Option(help="JSON de cenários")] = None,
    input: Annotated[str, typer.Option(help="Qual pergunta usar: completa|incompleta")] = (
        "completa"
    ),
    run_name: Annotated[str | None, typer.Option(help="Nome da run")] = None,
    resume: Annotated[bool, typer.Option(help="Retoma checkpoint")] = True,
) -> None:
    """Responde os cenários só com conhecimento geral do LLM (sem retrieval)."""
    if input not in ("completa", "incompleta"):
        deps.console.print("[red]--input deve ser 'completa' ou 'incompleta'.[/red]")
        raise typer.Exit(code=1)
    settings = deps.get_settings()
    scenarios_path = scenarios or (settings.questions_dir / "hypothesis_inicial_scenarios.json")
    if not scenarios_path.exists():
        alt = Path("data/hypothesis_inicial_scenarios.json")
        if alt.exists():
            scenarios_path = alt
    run_id = build_run_id(run_name, f"direct_{input}", datetime.now())
    setup_logging(settings, run_id=run_id)
    run_dir = settings.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    db_path = run_dir / "checkpoint.sqlite3"
    storage = SQLiteExecutionStorage(db_path)

    async def _run():
        items = await asyncio.to_thread(load_scenarios, scenarios_path)
        if not items:
            deps.console.print(f"[yellow]Nenhum cenário em {scenarios_path}[/yellow]")
            return
        completed = storage.get_completed_indices() if resume else set()
        engine = DirectLLMEngine(settings=settings)
        await engine.initialize()
        try:
            deps.console.print(
                f"[bold blue]run-direct: {len(items)} cenários | input={input} "
                f"| modelo={engine.llm_model} (sem grafo, sem cache)[/bold blue]"
            )
            sem = asyncio.Semaphore(2)
            manifest: list[dict] = []

            async def worker(idx: int, item: dict) -> None:
                if idx in completed:
                    return
                key = "pergunta_completa" if input == "completa" else "pergunta_incompleta"
                question = str(item.get(key, ""))
                async with sem:
                    start = time.perf_counter()
                    record = QueryExecutionRecord(
                        index=idx,
                        query=question,
                        mode=SearchMode.DIRECT,
                        top_k=0,
                        model=engine.llm_model,
                        source=QueryInteractionSource.BASELINE_ENGINE,
                    )
                    try:
                        resp = await engine.aquery(query=question, stream=False)
                        resp_text = str(resp or "")
                        record.response = resp_text
                        record.total_latency_seconds = round(time.perf_counter() - start, 4)
                        record.status = (
                            RagExecutionStatus.SUCCESS
                            if resp_text.strip()
                            else RagExecutionStatus.ERROR
                        )
                        if not resp_text.strip():
                            record.error_message = "Resposta vazia do LLM."
                    except Exception as e:
                        record.total_latency_seconds = round(time.perf_counter() - start, 4)
                        record.status = RagExecutionStatus.ERROR
                        record.error_message = f"{type(e).__name__}: {e}"
                    await asyncio.to_thread(storage.save_record, record)
                    manifest.append(
                        {
                            "index": idx,
                            "id": item.get("id", str(idx)),
                            "input": input,
                            "pergunta": question,
                            "ground_truth": item.get("ground_truth", ""),
                            "tipo": item.get("tipo", ""),
                        }
                    )

            await asyncio.gather(*(worker(i, it) for i, it in enumerate(items)))
            manifest.sort(key=lambda m: m["index"])
            records = await asyncio.to_thread(storage.load_all_records)
            csv_path = run_dir / "benchmark_analise_detalhada.csv"
            md_path = run_dir / "resumo_benchmark.md"
            manifest_path = run_dir / "direct_manifest.json"
            golden_path = run_dir / "golden.json"
            golden_entries = [
                {
                    "question": m["pergunta"],
                    "question_type": m["tipo"] or "UNMAPPED",
                    "ground_truth": m["ground_truth"],
                    "source_document": next(
                        (it.get("source_document", "") for it in items if it.get("id") == m["id"]),
                        "",
                    ),
                }
                for m in manifest
            ]
            await asyncio.to_thread(BenchmarkReporter.export_execution_csv, records, csv_path)
            await asyncio.to_thread(
                BenchmarkReporter.generate_execution_markdown_report, records, md_path
            )
            await asyncio.to_thread(
                manifest_path.write_text,
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            await asyncio.to_thread(
                golden_path.write_text,
                json.dumps(golden_entries, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            settings.results_dir.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(
                BenchmarkReporter.export_execution_csv,
                records,
                settings.results_dir / "benchmark_analise_detalhada.csv",
            )
            await asyncio.to_thread(
                BenchmarkReporter.generate_execution_markdown_report,
                records,
                settings.results_dir / "resumo_benchmark.md",
            )
            deps.console.print("\n[bold green]✅ run-direct finalizado![/bold green]")
            deps.console.print(f"📁 Checkpoint: [cyan]{db_path}[/cyan]")
            deps.console.print(f"📊 Relatório: [cyan]{md_path}[/cyan]")
            deps.console.print(f"Avalie depois com: [cyan]ragbench eval --run-id {run_id}[/cyan]")
        finally:
            await engine.finalize()

    asyncio.run(_run())
