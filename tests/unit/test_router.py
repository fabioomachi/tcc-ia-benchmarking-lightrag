"""Roteador só-grafo: scoring, margem, pergunta discriminativa e loop guiado."""

import json

from ragbench.conversational.batch import simulate_clarification_guided
from ragbench.conversational.router import (
    DOC_ACESSO,
    DOC_CDC,
    load_entity_index,
    next_discriminative_slot,
    normalize,
    route_by_graph,
    route_margin,
    score_docs,
)

FAKE_INDEX = {
    DOC_ACESSO: ["senha de 6 digitos", "alfa code", "biometria", "agencia"],
    DOC_CDC: ["cdc", "boleto", "amortizacao", "agencia"],
}


def test_normalize_tira_acento_e_caixa():
    assert normalize("Agência TÃO") == "agencia tao"
    assert normalize("Senha-8") == "senha-8"


def test_score_docs_pondera_tokens_exclusivos():
    scores = score_docs("senha de 6 digitos e alfa code", FAKE_INDEX)
    # acesso tem senha/digitos/alf/code; cdc só divide "agencia" (inexistente aqui)
    assert scores[DOC_ACESSO] > scores[DOC_CDC]
    assert scores[DOC_CDC] == 0.0


def test_score_docs_expansao_de_slots():
    scores = score_docs("minha senha bloqueou", FAKE_INDEX, filled={"codigo_bloqueio": "U"})
    assert scores[DOC_ACESSO] > 0


def test_route_margin():
    assert route_margin({"a": 0.5, "b": 0.2}) == 0.3
    assert route_margin({"a": 0.5}) == 0.0
    assert route_margin({}) == 0.0


def test_route_by_graph_confiante_e_estrategia():
    route = route_by_graph("bloqueio da senha de 6 digitos com alfa code", FAKE_INDEX, filled={})
    assert route["doc"] == DOC_ACESSO
    assert (route["mode"], route["top_k"]) == ("local", 10)
    assert route["confident"] is True


def test_route_by_graph_sem_overlap_cai_em_fallback():
    route = route_by_graph("xyz nada a ver", FAKE_INDEX)
    assert route["doc"] is None
    assert (route["mode"], route["top_k"]) == ("hybrid", 5)
    assert route["confident"] is False


def test_route_by_graph_sem_indice():
    route = route_by_graph("qualquer coisa", {})
    assert route["doc"] is None
    assert route["confident"] is False


def test_next_discriminative_slot_prioriza_acesso():
    assert next_discriminative_slot(["canal_tentado", "codigo_bloqueio"]) == "codigo_bloqueio"
    assert next_discriminative_slot([]) is None


def test_load_entity_index_mapeia_docs(tmp_path):
    storage = tmp_path / "graph"
    storage.mkdir()
    (storage / "kv_store_full_entities.json").write_text(
        json.dumps(
            {
                "h1": {"entity_names": ["Alfa Code", "TAA"]},
                "h2": {"entity_names": ["CDC", "Boleto"]},
            }
        ),
        encoding="utf-8",
    )
    (storage / "kv_store_doc_status.json").write_text(
        json.dumps(
            {
                "h1": {"content_summary": "DOCUMENTO_ORIGEM: pop_acesso_pf.md ..."},
                "h2": {"content_summary": "DOCUMENTO_ORIGEM: pop_cdc_pf.md ..."},
            }
        ),
        encoding="utf-8",
    )
    index = load_entity_index(storage)
    assert index[DOC_ACESSO] == ["alfa code", "taa"]
    assert index[DOC_CDC] == ["cdc", "boleto"]


def test_load_entity_index_sem_arquivos(tmp_path):
    assert load_entity_index(tmp_path / "vazio") == {}


def test_guided_para_cedo_quando_margem_estabiliza():
    filled, turns, enriched, route = simulate_clarification_guided(
        "Minha senha bloqueou, como desbloqueio pelo site?",
        {
            "codigo_bloqueio": "U",
            "alfa_code": "não",
            "biometria_dias": "5",
            "canal_tentado": "site",
            "tipo_cliente": "correntista",
        },
        entity_index=FAKE_INDEX,
        max_turns=3,
        margin_min=0.05,
    )
    assert turns >= 1
    assert route["doc"] == DOC_ACESSO
    assert "codigo_bloqueio=U" in enriched
    assert filled["codigo_bloqueio"] == "U"


def test_guided_sem_indice_preenche_como_classica():
    filled, turns, enriched, route = simulate_clarification_guided(
        "Quero cancelar meu CDC",
        {"tipo_cliente": "correntista", "canal_tentado": "app"},
        entity_index={},
        max_turns=3,
    )
    assert turns == 2
    assert route["doc"] is None
    assert "tipo_cliente=correntista" in enriched
    assert filled["canal_tentado"] == "app"


def test_routing_settings_default(tmp_path, monkeypatch):
    import os

    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(
            ("ROUTING__", "CLARIFY__", "OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__")
        ):
            monkeypatch.delenv(key, raising=False)
    from ragbench.config import BenchmarkSettings

    settings = BenchmarkSettings(_env_file=None)
    assert settings.routing.enabled is True
    assert settings.routing.margin_min == 0.05
    assert settings.routing.acesso_top_k == 10
