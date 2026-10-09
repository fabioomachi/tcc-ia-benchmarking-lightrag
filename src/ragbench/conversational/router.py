"""Roteador só-grafo para o spike da hipótese (puro, sem I/O de rede).

Decide entre N POPs pela sobreposição da query com as entidades reais do
índice (`kv_store_full_entities.json`), nunca por lista fixa de keywords.
A clarificação usa a margem entre docs como critério de parada e pergunta
primeiro o slot mais discriminativo — a "inteligência" do processo: cada
pergunta existe para aumentar a margem, não para cumprir tabela fixa.

Genérico: novos POPs são descobertos via `DOCUMENTO_ORIGEM: <arquivo>`
no `kv_store_doc_status.json`, sem hardcoded de nomes. Estratégias
tuned de acesso/CDC são mantidas como legado; demais docs usam o
default (hybrid/k5) ou overrides via `RoutingSettings.strategies`.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from pydantic import BaseModel, Field

DOC_ACESSO = "pop_acesso_pf.md"
DOC_CDC = "pop_cdc_pf.md"


class RouteInfo(BaseModel):
    """Decisão do roteador só-grafo (contrato tipado, sem dict genérico)."""

    doc: str | None = None
    mode: str = "hybrid"
    top_k: int = Field(default=5, ge=1, le=100)
    confident: bool = False
    margin: float = Field(default=0.0, ge=0.0)
    scores: dict[str, float] = Field(default_factory=dict)

    def __getitem__(self, key: str):
        """Acesso estilo dict (compat: callers/testes legados usam route["doc"])."""
        return getattr(self, key)

    def get(self, key: str, default=None):
        """Acesso estilo dict com default (compat: route.get("confident"))."""
        return getattr(self, key, default)


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
    "que como mais muito entre sobre após ate meu minha seu sua teu tua "
    "me mim te ti nos vos lhe lhes isso isto este esta esse essa aquele "
    "aquela aquilo estou esta nao".split()
)


def _tokens(text: str) -> list[str]:
    return [
        t
        for t in re.findall(r"[a-z0-9]+", normalize(text))
        if (len(t) >= 3 and t not in _STOPWORDS) or t.isdigit()
    ]


def slot_expansion_text(filled: dict[str, str]) -> str:
    """Traduz slots preenchidos para termos do vocabulário das entidades.

    Somente os hints desenhados por slot: os valores crus ("correntista",
    "app", "não") são atributos do cliente que casam por acaso com
    entidades ("não correntista", "app alfa") e dominavam o ranking com
    peso 1.0 exclusivo — ruído que inverte a rota em N POPs.
    """
    parts = [SLOT_ENTITY_HINTS.get(slot, "") for slot in filled]
    return " ".join(p for p in parts if p)


def build_token_weights(index: dict[str, list[str]]) -> dict[str, dict[str, float]]:
    """Peso por token: exclusivo de um doc vale 1.0, compartilhado vale 0.25.

    Evita que termos genéricos ("conta", "agencia", presentes em N docs)
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
# Legado 2-POPs mantido; novos POPs usam o default ou overrides via
# `RoutingSettings.strategies` (ver `strategy_for_doc()`).
STRATEGY_FOR_DOC: dict[str, tuple[str, int]] = {
    DOC_ACESSO: ("local", 10),
    DOC_CDC: ("hybrid", 5),
}
DEFAULT_STRATEGY = ("hybrid", 5)


def strategy_for_doc(
    doc: str,
    strategies: dict | None = None,
    default: tuple[str, int] = DEFAULT_STRATEGY,
) -> tuple[str, int]:
    """Estratégia de retrieval para um documento (genérica para N POPs).

    Precedência: overrides explícitos > `STRATEGY_FOR_DOC` legado > default.
    Aceita valores como tupla `(mode, top_k)` ou objeto com `.mode`/`.top_k`
    (ex: `DocStrategy` do settings) para evitar acoplamento com o config.
    """
    get = getattr(strategies, "get", None) if strategies else None
    if callable(get):
        override = get(doc)
        if override is not None:
            if isinstance(override, (tuple, list)) and len(override) == 2:
                return str(override[0]), int(override[1])
            mode = getattr(override, "mode", None)
            top_k = getattr(override, "top_k", None)
            if mode is not None and top_k is not None:
                return str(mode), int(top_k)
    return STRATEGY_FOR_DOC.get(doc, default)


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


_DOC_ORIGIN_RE = re.compile(r"DOCUMENTO_ORIGEM:\s*(\S+\.md)")


def extract_source_filename(summary: str) -> str:
    """Extrai o nome do POP de `DOCUMENTO_ORIGEM: <arquivo>` ("" se ausente).

    Genérico para N POPs: não há lista hardcoded de nomes — qualquer
    arquivo `.md` referenciado no `content_summary` é indexado.
    """
    m = _DOC_ORIGIN_RE.search(summary or "")
    return m.group(1) if m else ""


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
        source = extract_source_filename(str(summary))
        # Compat legada: resumos antigos sem o prefixo explícito.
        if not source:
            if "pop_acesso_pf" in str(summary):
                source = DOC_ACESSO
            elif "pop_cdc_pf" in str(summary):
                source = DOC_CDC
        if source:
            index[source] = [normalize(n) for n in names if n]
    return index


def score_docs(
    text: str,
    index: dict[str, list[str]],
    filled: dict[str, str] | None = None,
) -> dict[str, float]:
    """Recall ponderado da query sobre as entidades de cada doc (0..1).

    Tokens exclusivos de um doc valem 1.0; compartilhados, 0.25 — o que
    separa os POPs decide, não o vocabulário comum. O denominador é o
    número de tokens da query (igual para todos os docs), nunca o tamanho
    do documento: docs com poucas entidades não são mais inflados, o que
    torna o ranking correto para N POPs de tamanhos distintos. `filled`
    injeta a expansão dos slots (o valor cru "U" jamais casaria com
    entidade). Retorna {} se o índice estiver vazio.
    """
    if not index:
        return {}
    query = text if not filled else f"{text} {slot_expansion_text(filled)}"
    qtokens = set(_tokens(query))
    if not qtokens:
        return {doc: 0.0 for doc in index}
    weights = build_token_weights(index)
    denom = len(qtokens)
    scores: dict[str, float] = {}
    for doc, w in weights.items():
        scores[doc] = sum(v for t, v in w.items() if t in qtokens) / denom
    return scores


def route_margin(scores: dict[str, float]) -> float:
    """Margem entre o melhor e o segundo melhor doc (0.0 se <2 docs)."""
    ordered = sorted(scores.values(), reverse=True)
    if len(ordered) < 2:
        return 0.0
    return ordered[0] - ordered[1]


def keyword_hits(text: str) -> dict[str, int]:
    """Contagem de keywords de domínio por POP (import tardio, puro).

    Reusa as listas do `DecisionTreeEngine` (cobrem os 8 POPs com
    vocabulário normativo que o grafo pode não ter extraído como entidade,
    ex: "sisjud", "boleto"). Retorna {} se o módulo não estiver disponível
    (roteador recai no overlap puro do grafo).
    """
    try:
        from ragbench.engines.decision_tree_engine import (
            ACESSO_KEYWORDS,
            CDC_KEYWORDS,
            NEW_DOC_KEYWORDS,
        )
    except Exception:
        return {}
    norm = normalize(text or "")
    hits: dict[str, int] = {
        DOC_ACESSO: sum(1 for k in ACESSO_KEYWORDS if k in norm),
        DOC_CDC: sum(1 for k in CDC_KEYWORDS if k in norm),
    }
    for doc, kws in NEW_DOC_KEYWORDS.items():
        hits[doc] = sum(1 for k in kws if k in norm)
    return hits


def route_by_graph(
    text: str,
    index: dict[str, list[str]],
    margin_min: float = 0.05,
    filled: dict[str, str] | None = None,
    strategies: dict | None = None,
    default_strategy: tuple[str, int] = DEFAULT_STRATEGY,
) -> RouteInfo:
    """Roteia só com dados do grafo + vocabulário normativo. Retorna doc e estratégia.

    `confident` = margem >= margin_min. Sem índice ou sem overlap, doc=None
    e estratégia padrão (sem regressão vs comportamento anterior).
    `strategies` permite overrides por documento sem mexer no código
    (novos POPs); o default cobre qualquer doc não mapeado.

    O overlap do grafo é primário; as keywords de domínio (mesmo
    vocabulário da árvore de decisão) entram como bônus na mesma escala
    para desempatar casos em que o grafo extraiu poucas entidades do POP
    certo (ex: query curta com "sisjud" vs docs grandes com "extrato").
    """
    scores = score_docs(text, index, filled=filled)
    if not scores or all(v == 0 for v in scores.values()):
        return RouteInfo(
            doc=None,
            mode=default_strategy[0],
            top_k=default_strategy[1],
            confident=False,
            margin=0.0,
            scores=scores,
        )
    query = text if not filled else f"{text} {slot_expansion_text(filled)}"
    denom = max(1, len(set(_tokens(query))))
    hits = keyword_hits(text)
    if filled:
        extra = keyword_hits(slot_expansion_text(filled))
        hits = {d: hits.get(d, 0) + extra.get(d, 0) for d in set(hits) | set(extra)}
    combined = {d: s + hits.get(d, 0) / denom for d, s in scores.items()}
    for d, h in hits.items():
        if d not in combined and h > 0 and d in index:
            combined[d] = h / denom
    best = max(combined, key=lambda d: combined[d])
    margin = route_margin(combined)
    mode, top_k = strategy_for_doc(best, strategies, default_strategy)
    return RouteInfo(
        doc=best,
        mode=mode,
        top_k=top_k,
        confident=margin >= margin_min,
        margin=round(margin, 4),
        scores={d: round(v, 4) for d, v in combined.items()},
    )


def next_discriminative_slot(missing: list[str]) -> str | None:
    """Slot faltante mais discriminativo (genérico para N POPs).

    Prioriza a ordem legada acesso-específica (preserva comportamento nos
    2 POPs originais); slots desconhecidos (novos POPs) vêm depois, na
    ordem recebida — sem tabela por documento.
    """
    for slot in DISCRIMINATIVE_ORDER:
        if slot in missing:
            return slot
    return missing[0] if missing else None
