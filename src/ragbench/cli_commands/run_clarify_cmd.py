"""Comando `run-clarify`: batch da hipótese com os mesmos artefatos do `run`.

Fluxo por cenário (`data/hypothesis_inicial_scenarios.json`):
  pergunta_incompleta + slots_simulados
    -> clarificação guiada pelo grafo (para na margem entre N docs)
    -> roteamento só-grafo genérico (legado acesso=local/k10,
       cdc=hybrid/k5; demais POPs via default/overrides de settings)
    -> query roteada (linha legada `k=v` + resumo natural + rota) + system
       prompt de roteamento + histórico de turnos no `aquery`
    -> probe genérica de reparo se contexto fraco do doc previsto
    -> checkpoint.sqlite3 + CSV + MD (compatível com `eval --run-id`)
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from ragbench.cli_commands import deps
from ragbench.cli_commands.probe_cmd import classify_context_generic
from ragbench.cli_commands.quota_support import (
    QUOTA_EXIT_CODE,
    merge_run_manifest,
    print_quota_stopped,
)
from ragbench.cli_commands.run_cmd import build_run_id
from ragbench.conversational.batch import (
    load_scenarios,
    simulate_clarification,
    simulate_clarification_guided_full,
)
from ragbench.conversational.router import (
    DEFAULT_STRATEGY,
    DOC_ACESSO,
    DOC_CDC,
    load_entity_index,
)
from ragbench.core.exceptions import QuotaExhaustedError
from ragbench.core.models import (
    QueryExecutionRecord,
    QueryInteractionSource,
    RagExecutionStatus,
    SearchMode,
)
from ragbench.engines.lightrag_engine import LightRAGEngine
from ragbench.infrastructure.logging import setup_logging
from ragbench.infrastructure.storage import SQLiteExecutionStorage
from ragbench.reporting.reporters import BenchmarkReporter

# Legado: limiar fixo de reparo. Uso atual via
# `settings.routing.weak_markers_threshold` (default 5); mantido para
# compatibilidade com imports externos.
WEAK_CONTEXT_MARKERS = 5


def build_routing_strategies(settings) -> tuple[dict[str, tuple[str, int]], tuple[str, int]]:
    """Compõe overrides de estratégia + default a partir do settings (puro).

    Precedência por doc: `routing.strategies[doc]` > legado acesso/CDC do
    settings > `STRATEGY_FOR_DOC` do router > default hybrid/k5.
    """
    strategies: dict[str, tuple[str, int]] = {
        DOC_ACESSO: (settings.routing.acesso_mode, settings.routing.acesso_top_k),
        DOC_CDC: (settings.routing.cdc_mode, settings.routing.cdc_top_k),
    }
    for doc, strat in (settings.routing.strategies or {}).items():
        strategies[doc] = (strat.mode, strat.top_k)
    default = (settings.routing.default_mode, settings.routing.default_top_k)
    if default == ("hybrid", 5) and DEFAULT_STRATEGY != ("hybrid", 5):
        default = DEFAULT_STRATEGY
    return strategies, default


def run_clarify_batch(
    scenarios: Annotated[Path | None, typer.Option(help="JSON de cenários")] = None,
    mode: Annotated[str, typer.Option(help="Modo de busca")] = "hybrid",
    top_k: Annotated[int, typer.Option(help="Top-K")] = 5,
    max_clarify_turns: Annotated[int, typer.Option(help="Max turnos de clarificação")] = 3,
    run_name: Annotated[str | None, typer.Option(help="Nome da run")] = None,
    resume: Annotated[bool, typer.Option(help="Retoma checkpoint")] = True,
) -> None:
    """Executa os cenários incompletos com clarificação simulada + grafo.

    Sai com código 3 se a cota da API for esgotada (retome com o mesmo --run-name).
    """
    settings = deps.get_settings()
    scenarios_path = scenarios or (settings.questions_dir / "hypothesis_inicial_scenarios.json")
    if not scenarios_path.exists():
        # fallback para data/ na raiz quando questions_dir foi isolado em testes
        alt = Path("data/hypothesis_inicial_scenarios.json")
        if alt.exists():
            scenarios_path = alt
    search_mode = SearchMode(mode)
    run_id = build_run_id(run_name, f"clarify_{mode}", datetime.now())
    setup_logging(settings, run_id=run_id)
    run_dir = settings.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    db_path = run_dir / "checkpoint.sqlite3"
    storage = SQLiteExecutionStorage(db_path)
    routing_enabled = settings.routing.enabled
    entity_index = load_entity_index(settings.storage_dir) if routing_enabled else {}
    strategies, default_strategy = build_routing_strategies(settings)
    weak_threshold = settings.routing.weak_markers_threshold

    async def _run():
        items = await asyncio.to_thread(load_scenarios, scenarios_path)
        if not items:
            deps.console.print(f"[yellow]Nenhum cenário em {scenarios_path}[/yellow]")
            return
        completed = storage.get_completed_indices() if resume else set()
        engine = LightRAGEngine.for_chat(settings=settings)
        await engine.initialize()
        try:
            deps.console.print(
                f"[bold blue]run-clarify: {len(items)} cenários | modo={mode} "
                f"| clarify_turns={max_clarify_turns} "
                f"| roteador={'on' if routing_enabled else 'off'}[/bold blue]"
            )
            manifest: list[dict] = []
            quota_stop = False
            for idx, item in enumerate(items):
                if idx in completed:
                    continue
                q_incomplete = str(item.get("pergunta_incompleta", ""))
                simulated = dict(item.get("slots_simulados", {}))
                history: list[dict[str, str]] = []
                probe_ctx_preview = ""
                probe_counts: dict[str, int] = {}
                if routing_enabled:
                    filled, turns, enriched, route, history = simulate_clarification_guided_full(
                        q_incomplete,
                        simulated,
                        entity_index=entity_index,
                        max_turns=max_clarify_turns,
                        margin_min=settings.routing.margin_min,
                        strategies=strategies,
                        default_strategy=default_strategy,
                    )
                    eff_mode = SearchMode(route["mode"])
                    eff_top_k = int(route["top_k"])
                else:
                    filled, turns, enriched = simulate_clarification(
                        q_incomplete, simulated, max_turns=max_clarify_turns
                    )
                    route = {
                        "doc": None,
                        "mode": mode,
                        "top_k": top_k,
                        "confident": False,
                        "margin": 0.0,
                        "scores": {},
                    }
                    eff_mode, eff_top_k = search_mode, top_k
                # Probe de reparo genérica (N POPs): contexto fraco do doc
                # previsto -> 1 turno extra mirando slot discriminativo
                # restante (se simulado).
                repair_turns = 0
                if routing_enabled and route.get("doc"):
                    try:
                        probe_ctx = await engine.aget_context(
                            query=enriched, mode=eff_mode, top_k=eff_top_k
                        )
                        probe_ctx_preview = (probe_ctx or "")[:600].replace("\n", " ")
                        _, probe_counts = classify_context_generic(
                            probe_ctx or "",
                            docs=sorted(set(list(entity_index) + [str(route.get("doc"))])) or None,
                        )
                        own = probe_counts.get(str(route.get("doc")), 0)
                        if own < weak_threshold:
                            from ragbench.conversational.clarifier import (
                                build_enriched_query,
                                build_routed_query,
                                clarify_history_turn,
                                extract_slots,
                                find_missing_slots,
                                merge_slots,
                                question_for_slot,
                            )
                            from ragbench.conversational.router import (
                                next_discriminative_slot,
                                route_by_graph,
                            )

                            missing = find_missing_slots(filled, extra_slots=list(simulated))
                            target = next_discriminative_slot(
                                [s for s in missing if s in simulated]
                            )
                            if target is not None and turns + repair_turns < max_clarify_turns:
                                value = simulated[target]
                                answered = extract_slots(str(value), expected_slot=target)
                                if target not in answered:
                                    answered[target] = str(value)
                                filled = merge_slots(filled, answered)
                                repair_turns = 1
                                history.extend(
                                    clarify_history_turn(question_for_slot(target), str(value))
                                )
                                # Roteia sobre o texto legado: o Resumo cita o
                                # arquivo previsto e realimentaria o scoring.
                                provisional = build_enriched_query(q_incomplete, filled)
                                route = route_by_graph(
                                    provisional,
                                    entity_index,
                                    margin_min=settings.routing.margin_min,
                                    filled=filled,
                                    strategies=strategies,
                                    default_strategy=default_strategy,
                                )
                                enriched = build_routed_query(
                                    q_incomplete,
                                    filled,
                                    route_doc=route.get("doc"),
                                    margin=route.get("margin"),
                                    mode=route.get("mode"),
                                    top_k=route.get("top_k"),
                                )
                                eff_mode = SearchMode(route["mode"])
                                eff_top_k = int(route["top_k"])
                    except QuotaExhaustedError:
                        raise
                    except Exception:
                        pass
                start = time.perf_counter()
                record = QueryExecutionRecord(
                    index=idx,
                    query=enriched,
                    mode=eff_mode,
                    top_k=eff_top_k,
                    model=engine.llm_model,
                )
                try:
                    # Histórico de turnos: a IA recebe o diálogo estruturado
                    # além da query achatada (fake engine de testes ignora).
                    try:
                        resp = await engine.aquery(
                            query=enriched,
                            mode=eff_mode,
                            top_k=eff_top_k,
                            stream=False,
                            history_messages=history or None,
                        )
                    except TypeError:
                        resp = await engine.aquery(
                            query=enriched, mode=eff_mode, top_k=eff_top_k, stream=False
                        )
                    if not isinstance(resp, str) and hasattr(resp, "__aiter__"):
                        full = ""
                        async for chunk in resp:
                            full += chunk
                        resp_text = full
                    else:
                        resp_text = str(resp or "")
                    record.response = resp_text
                    record.source = QueryInteractionSource.LIGHTRAG_ENGINE
                    record.total_latency_seconds = round(time.perf_counter() - start, 4)
                    record.status = (
                        record.status.__class__.SUCCESS
                        if resp_text.strip()
                        else record.status.__class__.ERROR
                    )
                    if not resp_text.strip():
                        record.error_message = "Resposta vazia do engine."
                except QuotaExhaustedError as e:
                    record.total_latency_seconds = round(time.perf_counter() - start, 4)
                    record.status = RagExecutionStatus.ERROR
                    record.error_message = f"QuotaExhaustedError: {e}"
                    await asyncio.to_thread(storage.save_record, record)
                    quota_stop = True
                    break
                except Exception as e:
                    record.total_latency_seconds = round(time.perf_counter() - start, 4)
                    record.status = record.status.__class__.ERROR
                    record.error_message = f"{type(e).__name__}: {e}"
                await asyncio.to_thread(storage.save_record, record)
                manifest.append(
                    {
                        "index": idx,
                        "id": item.get("id", str(idx)),
                        "pergunta_incompleta": q_incomplete,
                        "slots_preenchidos": filled,
                        "clarify_turns": turns + repair_turns,
                        "repair_turns": repair_turns,
                        "rota_doc": route.get("doc"),
                        "rota_mode": route.get("mode"),
                        "rota_top_k": route.get("top_k"),
                        "rota_margin": route.get("margin"),
                        "rota_confident": route.get("confident"),
                        "rota_scores": route.get("scores"),
                        "query_enriquecida": enriched,
                        "historico_clarify": history,
                        "probe_ctx_preview": probe_ctx_preview,
                        "probe_counts": probe_counts,
                        "ground_truth": item.get("ground_truth", ""),
                        "tipo": item.get("tipo", ""),
                    }
                )
            records = await asyncio.to_thread(storage.load_all_records)
            csv_path = run_dir / "benchmark_analise_detalhada.csv"
            md_path = run_dir / "resumo_benchmark.md"
            manifest_path = run_dir / "clarify_manifest.json"
            golden_path = run_dir / "golden.json"
            manifest = merge_run_manifest(manifest, manifest_path)
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
            # Cópia legada em resultados/ (mesmo padrão do run)
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
            if quota_stop:
                done = storage.get_completed_indices()
                scenarios_opt = f" --scenarios {scenarios_path}" if scenarios else ""
                print_quota_stopped(
                    deps.console,
                    resume_cmd=(
                        f"uv run ragbench run-clarify --run-name {run_id} "
                        f"--mode {mode} --top-k {top_k}{scenarios_opt}"
                    ),
                    remaining=len(items) - len(done),
                    checkpoint=db_path,
                )
                raise typer.Exit(code=QUOTA_EXIT_CODE)
            deps.console.print("\n[bold green]✅ run-clarify finalizado![/bold green]")
            deps.console.print(f"📁 Checkpoint: [cyan]{db_path}[/cyan]")
            deps.console.print(f"📑 Manifest clarify: [cyan]{manifest_path}[/cyan]")
            deps.console.print(f"📊 Relatório: [cyan]{md_path}[/cyan]")
            deps.console.print(f"Avalie depois com: [cyan]ragbench eval --run-id {run_id}[/cyan]")
        finally:
            await engine.finalize()

    asyncio.run(_run())
