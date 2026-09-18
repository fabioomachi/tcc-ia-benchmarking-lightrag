"""Comando `run-tree`: chatbot tradicional (árvore) nos 24 cenários.

Fluxo por cenário: pergunta_incompleta + slots_simulados -> clarificação
simulada (preenche tudo, determinístico) -> DecisionTreeEngine.decide ->
template fixo. Zero LLM, zero grafo, zero custo. Mesmos artefatos do `run`
(checkpoint + CSV + MD + `golden.json`), records com `mode=tree` +
`source=tree_engine`. Avaliável com `eval --run-id`.
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
from ragbench.conversational.batch import load_scenarios, simulate_clarification
from ragbench.core.models import (
    QueryExecutionRecord,
    QueryInteractionSource,
    RagExecutionStatus,
    SearchMode,
)
from ragbench.engines.decision_tree_engine import DecisionTreeEngine, decide
from ragbench.infrastructure.logging import setup_logging
from ragbench.infrastructure.storage import SQLiteExecutionStorage
from ragbench.reporting.reporters import BenchmarkReporter


def run_tree_batch(
    scenarios: Annotated[Path | None, typer.Option(help="JSON de cenários")] = None,
    max_clarify_turns: Annotated[int, typer.Option(help="Max turnos de clarificação")] = 3,
    run_name: Annotated[str | None, typer.Option(help="Nome da run")] = None,
    resume: Annotated[bool, typer.Option(help="Retoma checkpoint")] = True,
) -> None:
    """Responde os cenários com a árvore de decisão (regras fixas dos POPs)."""
    settings = deps.get_settings()
    scenarios_path = scenarios or (settings.questions_dir / "hypothesis_inicial_scenarios.json")
    if not scenarios_path.exists():
        alt = Path("data/hypothesis_inicial_scenarios.json")
        if alt.exists():
            scenarios_path = alt
    run_id = build_run_id(run_name, "tree", datetime.now())
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
        engine = DecisionTreeEngine(settings=settings)
        await engine.initialize()
        try:
            deps.console.print(
                f"[bold blue]run-tree: {len(items)} cenários | "
                f"árvore {engine.llm_model} (sem LLM, sem grafo)[/bold blue]"
            )
            manifest: list[dict] = []
            for idx, item in enumerate(items):
                if idx in completed:
                    continue
                q_incomplete = str(item.get("pergunta_incompleta", ""))
                simulated = dict(item.get("slots_simulados", {}))
                filled, turns, enriched = simulate_clarification(
                    q_incomplete, simulated, max_turns=max_clarify_turns
                )
                decision = await asyncio.to_thread(decide, enriched)
                start = time.perf_counter()
                record = QueryExecutionRecord(
                    index=idx,
                    query=enriched,
                    mode=SearchMode.TREE,
                    top_k=0,
                    model=engine.llm_model,
                    source=QueryInteractionSource.TREE_ENGINE,
                    response=decision.answer,
                    status=RagExecutionStatus.SUCCESS,
                    total_latency_seconds=round(time.perf_counter() - start, 4),
                )
                await asyncio.to_thread(storage.save_record, record)
                manifest.append(
                    {
                        "index": idx,
                        "id": item.get("id", str(idx)),
                        "branch": decision.branch,
                        "doc": decision.doc,
                        "confident": decision.confident,
                        "slots_preenchidos": filled,
                        "clarify_turns": turns,
                        "query_enriquecida": enriched,
                        "ground_truth": item.get("ground_truth", ""),
                        "tipo": item.get("tipo", ""),
                    }
                )
            records = await asyncio.to_thread(storage.load_all_records)
            csv_path = run_dir / "benchmark_analise_detalhada.csv"
            md_path = run_dir / "resumo_benchmark.md"
            manifest_path = run_dir / "tree_manifest.json"
            golden_path = run_dir / "golden.json"
            golden_entries = [
                {
                    "question": m["query_enriquecida"],
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
            deps.console.print("\n[bold green]✅ run-tree finalizado![/bold green]")
            deps.console.print(f"📁 Checkpoint: [cyan]{db_path}[/cyan]")
            deps.console.print(f"📑 Manifest árvore: [cyan]{manifest_path}[/cyan]")
            deps.console.print(f"Avalie depois com: [cyan]ragbench eval --run-id {run_id}[/cyan]")
        finally:
            await engine.finalize()

    asyncio.run(_run())
