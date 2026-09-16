"""Comando `chat-clarify` (spike hipótese): coleta slots antes do grafo."""

import asyncio
import sys
import time
from typing import Annotated

import typer
from rich.panel import Panel

from ragbench.cli_commands import deps
from ragbench.cli_commands.chat_cmd import apply_chat_model_override
from ragbench.config import BenchmarkSettings
from ragbench.conversational.clarifier import (
    build_enriched_query,
    extract_slots,
    find_missing_slots,
    merge_slots,
    next_clarifying_question,
    should_ask_more,
)
from ragbench.conversational.router import (
    load_entity_index,
    next_discriminative_slot,
    route_by_graph,
)
from ragbench.core.exceptions import OllamaConnectionError
from ragbench.core.models import SearchMode
from ragbench.engines.lightrag_engine import LightRAGEngine
from ragbench.infrastructure.semantic_cache import SemanticCache, SlidingWindowHistory


def collect_slots_interactive(
    initial_query: str,
    console_input,
    console_print,
    max_turns: int,
    entity_index: dict | None = None,
    margin_min: float = 0.05,
) -> tuple[dict[str, str], int, dict]:
    """Loop de clarificação guiado pelo grafo (testável sem console real).

    Pergunta o slot faltante mais discriminativo e para quando a margem do
    roteador estabiliza (além do limite de turnos). Retorna (filled, turns,
    route). Sem índice, recai na ordem canônica de slots.
    """
    from ragbench.conversational.clarifier import _SLOT_BY_NAME

    index = entity_index or {}
    filled = extract_slots(initial_query)
    turns = 0
    route: dict = route_by_graph(initial_query, index, margin_min=margin_min, filled=filled)
    while True:
        missing = find_missing_slots(filled)
        if not should_ask_more(missing, turns, max_turns):
            break
        if turns > 0 and route.get("confident"):
            break
        target = next_discriminative_slot(missing)
        slot = _SLOT_BY_NAME.get(target) if target else None
        question = slot.question if slot else next_clarifying_question(missing)
        if question is None:
            break
        console_print(f"[bold cyan]Para te responder melhor: {question}[/bold cyan]")
        try:
            answer = console_input("Resposta > ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not answer:
            break
        if answer.lower() in {"sair", "exit", "quit"}:
            break
        turns += 1
        filled = merge_slots(filled, extract_slots(answer, expected_slot=target))
        route = route_by_graph(
            build_enriched_query(initial_query, filled),
            index,
            margin_min=margin_min,
            filled=filled,
        )
    route = route_by_graph(
        build_enriched_query(initial_query, filled),
        index,
        margin_min=margin_min,
        filled=filled,
    )
    return filled, turns, route


def interactive_clarify_chat(
    mode: Annotated[str, typer.Option(help="Modo de busca")] = "hybrid",
    top_k: Annotated[int, typer.Option(help="Top-K entidades")] = 5,
    chat_model: Annotated[str | None, typer.Option(help="Override do modelo")] = None,
    max_clarify_turns: Annotated[int, typer.Option(help="Max turnos de clarificação")] = 3,
) -> None:
    """Chat com clarificação: pergunta o que falta antes de consultar o grafo."""
    settings: BenchmarkSettings = apply_chat_model_override(deps.get_settings(), chat_model)
    if max_clarify_turns <= 0:
        max_clarify_turns = settings.clarify.max_turns
    search_mode = SearchMode(mode)
    cache = SemanticCache(threshold=settings.cache_threshold)
    history = SlidingWindowHistory(max_turns=settings.history_turns)
    entity_index = load_entity_index(settings.storage_dir) if settings.routing.enabled else {}
    margin_min = settings.routing.margin_min

    async def _loop():
        engine = LightRAGEngine.for_chat(settings=settings)
        await engine.initialize()
        try:
            deps.console.print(
                Panel(
                    "[bold green]ragbench Chat-Clarify (spike hipótese)[/bold green]\n"
                    f"Modo: [cyan]{mode}[/cyan] | Top-K: [cyan]{top_k}[/cyan] | "
                    f"Clarify turns: [cyan]{max_clarify_turns}[/cyan]\n"
                    "O assistente pergunta os dados faltantes antes do grafo.\n"
                    "Digite [bold red]'sair'[/bold red] para encerrar.",
                    title="Sessão Clarify",
                )
            )
            while True:
                try:
                    query = deps.console.input("\n[bold yellow]Pergunta > [/bold yellow]").strip()
                    if query.lower() in ["sair", "exit", "quit"]:
                        break
                    if not query:
                        continue
                    start_time = time.perf_counter()
                    filled, clarify_turns, route = await asyncio.to_thread(
                        collect_slots_interactive,
                        query,
                        lambda p: deps.console.input(f"\n[bold yellow]{p}[/bold yellow]"),
                        deps.console.print,
                        max_clarify_turns,
                        entity_index,
                        margin_min,
                    )
                    if settings.routing.enabled and route.get("doc"):
                        eff_mode, eff_top_k = SearchMode(route["mode"]), int(route["top_k"])
                    else:
                        eff_mode, eff_top_k = search_mode, top_k
                    missing = find_missing_slots(filled)
                    enriched = build_enriched_query(query, filled)
                    deps.console.print(
                        f"[dim]Slots: {filled or '{}'} | "
                        f"faltando: {missing or 'nenhum'} | "
                        f"turnos clarify: {clarify_turns} | "
                        f"rota: {route.get('doc') or 'padrão'} "
                        f"({route.get('mode')}/{route.get('top_k')})[/dim]"
                    )
                    query_embs = await engine.get_query_embeddings([enriched])
                    if len(query_embs) > 0:
                        cached_resp, similarity = cache.get(query_embs[0])
                        if cached_resp:
                            latency = time.perf_counter() - start_time
                            deps.console.print(
                                "\n[green]⚡ Resposta (cache "
                                f"{similarity:.3f} | {latency:.3f}s):[/green]"
                            )
                            deps.console.print(cached_resp)
                            history.add_turn(enriched, cached_resp)
                            continue
                    deps.console.print(
                        f"\n[blue]🤖 Resposta Gerada ({eff_mode.value} | {engine.llm_model} "
                        f"| clarify={clarify_turns}):[/blue]"
                    )
                    response_gen = await engine.aquery(
                        enriched,
                        mode=eff_mode,
                        top_k=eff_top_k,
                        stream=True,
                        history_messages=history.get_messages(),
                    )
                    first_token = True
                    ttft = 0.0
                    full_text = ""
                    if isinstance(response_gen, str):
                        ttft = time.perf_counter() - start_time
                        full_text = response_gen
                        deps.console.print(full_text)
                    else:
                        async for chunk in response_gen:
                            if first_token:
                                ttft = time.perf_counter() - start_time
                                first_token = False
                            sys.stdout.write(chunk)
                            sys.stdout.flush()
                            full_text += chunk
                        if first_token:
                            ttft = time.perf_counter() - start_time
                    total_latency = time.perf_counter() - start_time
                    deps.console.print(
                        f"\n\n[dim]⏱ Total: {total_latency:.3f}s | TTFT: {ttft:.3f}s "
                        f"| clarify_turns: {clarify_turns}[/dim]"
                    )
                    if full_text.strip():
                        if len(query_embs) > 0:
                            cache.add(query_embs[0], full_text)
                        history.add_turn(enriched, full_text)
                except KeyboardInterrupt:
                    break
                except OllamaConnectionError as e:
                    deps.console.print(f"[red]Falha resiliente esgotada: {e}[/red]")
                except Exception as e:
                    deps.console.print(f"[red]Erro no processamento: {e}[/red]")
        finally:
            await engine.finalize()
            deps.console.print("[yellow]Sessão clarify encerrada.[/yellow]")

    asyncio.run(_loop())
