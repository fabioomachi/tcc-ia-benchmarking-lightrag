"""Roteador só-grafo para o spike da hipótese (puro, sem I/O de rede).

Decide acesso-vs-CDC pela sobreposição da query com as entidades reais do
índice (`kv_store_full_entities.json`), nunca por lista fixa de keywords.
A clarificação usa a margem entre docs como critério de parada e pergunta
primeiro o slot mais discriminativo — a "inteligência" do processo: cada
pergunta existe para aumentar a margem, não para cumprir tabela fixa.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

DOC_ACESSO = "pop_acesso_pf.md"
DOC_CDC = "pop_cdc_pf.md"

# Slots expandidos para o vocabulário das entidades do índice: o valor cru
# do slot (ex: "U") nunca apareceria num nome de entidade, então cada slot
# preenchido injeta os termos-entidade que ele implica. Continua só-grafo:
# a decisão sai do overlap com o índice, não de lista de keywords da query.
SLOT_ENTITY_HINTS = {
    "codigo_bloqueio": "senha de 6 digitos senha de 8 digitos bloqueio codigo",
    "alfa_code": "alfa code",
    "biometria_dias": "biometria",
    "canal_tentado": "",
    "tipo_cliente": "",
}

_STOPWORDS = frozenset(
    "de da do das dos e em no na nos nas para com por uma um os as o a se ao "
    "que como mais muito entre sobre após ate".split()
)


def _tokens(text: str) -> list[str]:
    return [
        t
        for t in re.findall(r"[a-z0-9]+", normalize(text))
        if (len(t) >= 3 and t not in _STOPWORDS) or t.isdigit()
    ]


def slot_expansion_text(filled: dict[str, str]) -> str:
    """Traduz slots preenchidos para termos do vocabulário das entidades."""
    parts = [SLOT_ENTITY_HINTS.get(slot, "") for slot in filled]
    parts += [str(v) for v in filled.values()]
    return " ".join(p for p in parts if p)


def build_token_weights(index: dict[str, list[str]]) -> dict[str, dict[str, float]]:
    """Peso por token: exclusivo de um doc vale 1.0, compartilhado vale 0.25.

    Evita que termos genéricos ("conta", "agencia", presentes nos dois docs)
    decidam a rota — o que separa é o vocabulário próprio de cada POP.
    """
    doc_token_sets = {doc: set() for doc in index}
    for doc, names in index.items():
        for name in names:
            doc_token_sets[doc].update(_tokens(name))
    weights: dict[str, dict[str, float]] = {}
    for doc, tokens in doc_token_sets.items():
        others = set().union(*(t for d, t in doc_token_sets.items() if d != doc))
        weights[doc] = {t: (0.25 if t in others else 1.0) for t in tokens}
    return weights


# Estratégias vencedoras da probe (5 piores + checagem CDC).
STRATEGY_FOR_DOC: dict[str, tuple[str, int]] = {
    DOC_ACESSO: ("local", 10),
    DOC_CDC: ("hybrid", 5),
}
DEFAULT_STRATEGY = ("hybrid", 5)

# Slots que mais separam os docs (acesso-específicos primeiro).
DISCRIMINATIVE_ORDER = [
    "codigo_bloqueio",
    "alfa_code",
    "biometria_dias",
    "tipo_cliente",
    "canal_tentado",
]


def normalize(text: str) -> str:
    """Minúsculas sem acento para comparar query com nomes de entidades."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def load_entity_index(storage_dir: Path) -> dict[str, list[str]]:
    """Carrega {source_document: [entidades normalizadas]} do índice em disco.

    Retorna {} se os arquivos não existirem (roteador cai em fallback).
    Função de I/O isolada: o scoring em si é puro.
    """
    entities_path = Path(storage_dir) / "kv_store_full_entities.json"
    status_path = Path(storage_dir) / "kv_store_doc_status.json"
    if not entities_path.exists() or not status_path.exists():
        return {}
    try:
        entities = json.loads(entities_path.read_text(encoding="utf-8"))
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    index: dict[str, list[str]] = {}
    for doc_id, payload in entities.items():
        names = payload.get("entity_names", []) if isinstance(payload, dict) else []
        summary = status.get(doc_id, {}).get("content_summary", "")
        source = ""
        if "pop_acesso_pf" in summary:
            source = DOC_ACESSO
        elif "pop_cdc_pf" in summary:
            source = DOC_CDC
        if source:
            index[source] = [normalize(n) for n in names if n]
    return index


def score_docs(
    text: str,
    index: dict[str, list[str]],
    filled: dict[str, str] | None = None,
) -> dict[str, float]:
    """Overlap ponderado entre a query e os tokens das entidades do índice.

    Tokens exclusivos de um doc valem 1.0; compartilhados, 0.25 — o que
    separa os POPs decide, não o vocabulário comum. `filled` injeta a
    expansão dos slots (o valor cru "U" jamais casaria com entidade).
    Retorna {} se o índice estiver vazio.
    """
    if not index:
        return {}
    query = text if not filled else f"{text} {slot_expansion_text(filled)}"
    qtokens = set(_tokens(query))
    if not qtokens:
        return {doc: 0.0 for doc in index}
    weights = build_token_weights(index)
    scores: dict[str, float] = {}
    for doc, w in weights.items():
        total = sum(w.values())
        if not total:
            scores[doc] = 0.0
            continue
        scores[doc] = sum(v for t, v in w.items() if t in qtokens) / total
    return scores


def route_margin(scores: dict[str, float]) -> float:
    """Margem entre o melhor e o segundo melhor doc (0.0 se <2 docs)."""
    ordered = sorted(scores.values(), reverse=True)
    if len(ordered) < 2:
        return 0.0
    return ordered[0] - ordered[1]


def route_by_graph(
    text: str,
    index: dict[str, list[str]],
    margin_min: float = 0.05,
    filled: dict[str, str] | None = None,
) -> dict:
    """Roteia só com dados do grafo. Retorna doc, estratégia e confiança.

    `confident` = margem >= margin_min. Sem índice ou sem overlap, doc=None
    e estratégia padrão (sem regressão vs comportamento anterior).
    """
    scores = score_docs(text, index, filled=filled)
    if not scores or all(v == 0 for v in scores.values()):
        return {
            "doc": None,
            "mode": DEFAULT_STRATEGY[0],
            "top_k": DEFAULT_STRATEGY[1],
            "confident": False,
            "margin": 0.0,
            "scores": scores,
        }
    best = max(scores, key=lambda d: scores[d])
    margin = route_margin(scores)
    mode, top_k = STRATEGY_FOR_DOC.get(best, DEFAULT_STRATEGY)
    return {
        "doc": best,
        "mode": mode,
        "top_k": top_k,
        "confident": margin >= margin_min,
        "margin": round(margin, 4),
        "scores": {d: round(v, 4) for d, v in scores.items()},
    }


def next_discriminative_slot(missing: list[str]) -> str | None:
    """Slot faltante mais discriminativo (ordem acesso-específicos primeiro)."""
    for slot in DISCRIMINATIVE_ORDER:
        if slot in missing:
            return slot
    return missing[0] if missing else None
