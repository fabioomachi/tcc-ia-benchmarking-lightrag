"""Módulo conversacional (spike hipótese): clarificação por slots sobre o grafo."""

from ragbench.conversational.batch import (
    load_scenarios,
    simulate_clarification,
    simulate_clarification_guided,
)
from ragbench.conversational.clarifier import (
    BANKING_SLOTS,
    build_enriched_query,
    extract_slots,
    find_missing_slots,
    next_clarifying_question,
    should_ask_more,
)
from ragbench.conversational.router import (
    DOC_ACESSO,
    DOC_CDC,
    build_token_weights,
    load_entity_index,
    next_discriminative_slot,
    route_by_graph,
    route_margin,
    score_docs,
    slot_expansion_text,
)

__all__ = [
    "BANKING_SLOTS",
    "DOC_ACESSO",
    "DOC_CDC",
    "build_enriched_query",
    "build_token_weights",
    "extract_slots",
    "find_missing_slots",
    "load_entity_index",
    "load_scenarios",
    "next_clarifying_question",
    "next_discriminative_slot",
    "route_by_graph",
    "route_margin",
    "score_docs",
    "should_ask_more",
    "simulate_clarification",
    "simulate_clarification_guided",
    "slot_expansion_text",
]
