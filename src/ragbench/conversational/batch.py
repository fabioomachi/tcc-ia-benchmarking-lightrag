"""Simulação batch da hipótese (pura, sem I/O de rede).

Replica o loop interativo de forma determinística: para cada slot faltante,
o "usuário simulado" responde com o valor de `slots_simulados` do cenário.
Isso permite comparar single-turn vs clarify no mesmo `eval` RAGAS.
"""

from __future__ import annotations

import json
from pathlib import Path

from ragbench.conversational.clarifier import (
    build_enriched_query,
    build_routed_query,
    clarify_history_turn,
    extract_slots,
    find_missing_slots,
    merge_slots,
    question_for_slot,
    should_ask_more,
)
from ragbench.conversational.router import (
    DEFAULT_STRATEGY,
    RouteInfo,
    next_discriminative_slot,
    route_by_graph,
)


def load_scenarios(path: Path) -> list[dict]:
    """Carrega os cenários de hipótese (lista de dicts)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    raise ValueError(f"Cenários inválidos em {path}: esperado lista")


def simulate_clarification(
    initial_query: str,
    simulated_slots: dict[str, str],
    max_turns: int = 3,
) -> tuple[dict[str, str], int, str]:
    """Simula o diálogo de clarificação sem interação real.

    Retorna (filled, turns, enriched_query). Cada turno preenche o próximo
    slot faltante se houver valor simulado; senão interrompe (usuário real
    não saberia responder).
    """
    filled = extract_slots(initial_query)
    turns = 0
    while True:
        # Genérico: inclui chaves simuladas de novos POPs além das canônicas.
        missing = find_missing_slots(filled, extra_slots=list(simulated_slots))
        if not should_ask_more(missing, turns, max_turns):
            break
        # Preenche o próximo slot faltante que tenha valor simulado; pula os
        # demais em vez de travar (ex: cenário CDC não tem codigo_bloqueio).
        next_slot: str | None = next((s for s in missing if s in simulated_slots), None)
        if next_slot is None:
            break
        value = simulated_slots[next_slot]
        # Simula a resposta do usuário e re-extrai com contexto do slot.
        answered = extract_slots(str(value), expected_slot=next_slot)
        if next_slot not in answered:
            answered[next_slot] = str(value)
        filled = merge_slots(filled, answered)
        turns += 1
    return filled, turns, build_enriched_query(initial_query, filled)


def simulate_clarification_guided(
    initial_query: str,
    simulated_slots: dict[str, str],
    entity_index: dict[str, list[str]] | None = None,
    max_turns: int = 3,
    margin_min: float = 0.05,
    strategies: dict | None = None,
    default_strategy: tuple[str, int] = DEFAULT_STRATEGY,
) -> tuple[dict[str, str], int, str, RouteInfo]:
    """Diálogo guiado pelo grafo: para quando a margem entre docs estabiliza.

    A cada turno pergunta o slot faltante mais discriminativo (não o próximo
    da lista fixa) e re-avalia a rota. Para quando (margem >= margin_min E ao
    menos 1 turno) ou sem valores simulados ou sem turnos. Sem índice, recai
    no comportamento da `simulate_clarification` clássica.
    Retorna (filled, turns, enriched_query, route_info como RouteInfo).

    A query enriquecida mantém a linha legada `k=v` e apenda o bloco
    `[Resumo para o assistente]` (ver `build_routed_query`).
    """
    filled, turns, enriched, route, _ = simulate_clarification_guided_full(
        initial_query,
        simulated_slots,
        entity_index=entity_index,
        max_turns=max_turns,
        margin_min=margin_min,
        strategies=strategies,
        default_strategy=default_strategy,
    )
    return filled, turns, enriched, route


def simulate_clarification_guided_full(
    initial_query: str,
    simulated_slots: dict[str, str],
    entity_index: dict[str, list[str]] | None = None,
    max_turns: int = 3,
    margin_min: float = 0.05,
    strategies: dict | None = None,
    default_strategy: tuple[str, int] = DEFAULT_STRATEGY,
) -> tuple[dict[str, str], int, str, RouteInfo, list[dict[str, str]]]:
    """Variante com histórico de turnos para o `aquery` (pura, sem I/O).

    Retorna (filled, turns, enriched_query, route, history_messages), onde
    o histórico reproduz pergunta/resposta de cada turno simulado para a
    IA receber o diálogo estruturado além da query achatada.
    """
    index = entity_index or {}
    filled = extract_slots(initial_query)
    turns = 0
    history: list[dict[str, str]] = []
    route = route_by_graph(
        initial_query,
        index,
        margin_min=margin_min,
        filled=filled,
        strategies=strategies,
        default_strategy=default_strategy,
    )
    while True:
        missing = find_missing_slots(filled, extra_slots=list(simulated_slots))
        if not should_ask_more(missing, turns, max_turns):
            break
        if turns > 0 and route.get("confident"):
            break
        target = next_discriminative_slot(
            [s for s in missing if s in simulated_slots]
        ) or next_discriminative_slot(missing)
        if target is None or target not in simulated_slots:
            break
        value = simulated_slots[target]
        answered = extract_slots(str(value), expected_slot=target)
        if target not in answered:
            answered[target] = str(value)
        filled = merge_slots(filled, answered)
        turns += 1
        history.extend(clarify_history_turn(question_for_slot(target), str(value)))
        provisional = build_enriched_query(initial_query, filled)
        route = route_by_graph(
            provisional,
            index,
            margin_min=margin_min,
            filled=filled,
            strategies=strategies,
            default_strategy=default_strategy,
        )
    # Roteamento final SEMPRE sobre o texto legado (sem Resumo): o bloco
    # [Resumo para o assistente] cita o nome do arquivo previsto
    # ("..._acesso_....md"), cujos tokens realimentariam o scoring e
    # tornariam qualquer rota intermediária auto-confirmatória.
    legacy = build_enriched_query(initial_query, filled)
    route = route_by_graph(
        legacy,
        index,
        margin_min=margin_min,
        filled=filled,
        strategies=strategies,
        default_strategy=default_strategy,
    )
    enriched = build_routed_query(
        initial_query,
        filled,
        route_doc=route.get("doc"),
        margin=route.get("margin"),
        mode=route.get("mode"),
        top_k=route.get("top_k"),
    )
    return filled, turns, enriched, route, history
