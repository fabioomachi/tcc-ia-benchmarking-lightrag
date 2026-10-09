"""Roteado genérico N-POPs: router, clarifier, batch, engine e probe."""

import json

from ragbench.cli_commands.probe_cmd import (
    classify_context_generic,
    doc_markers_for,
)
from ragbench.cli_commands.run_clarify_cmd import build_routing_strategies
from ragbench.config import BenchmarkSettings
from ragbench.conversational.batch import (
    simulate_clarification,
    simulate_clarification_guided,
    simulate_clarification_guided_full,
)
from ragbench.conversational.clarifier import (
    build_enriched_query,
    build_routed_instruction,
    build_routed_query,
    clarify_history_turn,
    extract_slots,
    find_missing_slots,
    question_for_slot,
)
from ragbench.conversational.router import (
    DOC_ACESSO,
    extract_source_filename,
    load_entity_index,
    route_by_graph,
    strategy_for_doc,
)
from ragbench.engines.lightrag_engine import (
    ROUTED_SYSTEM_SUFFIX,
    build_llm_messages,
)


def test_extract_source_filename_generico():
    assert extract_source_filename("DOCUMENTO_ORIGEM: POP_X_anon.md ...") == "POP_X_anon.md"
    assert extract_source_filename("sem marcador") == ""
    assert extract_source_filename("") == ""


def test_load_entity_index_generico_3_docs(tmp_path):
    storage = tmp_path / "graph"
    storage.mkdir()
    (storage / "kv_store_full_entities.json").write_text(
        json.dumps(
            {
                "h1": {"entity_names": ["Alfa Code"]},
                "h2": {"entity_names": ["CDC"]},
                "h3": {"entity_names": ["Fatura Email"]},
            }
        ),
        encoding="utf-8",
    )
    (storage / "kv_store_doc_status.json").write_text(
        json.dumps(
            {
                "h1": {"content_summary": "DOCUMENTO_ORIGEM: pop_acesso_pf.md x"},
                "h2": {"content_summary": "DOCUMENTO_ORIGEM: pop_cdc_pf.md x"},
                "h3": {"content_summary": "DOCUMENTO_ORIGEM: POP_Fatura_Y.md x"},
            }
        ),
        encoding="utf-8",
    )
    index = load_entity_index(storage)
    assert set(index) == {"pop_acesso_pf.md", "pop_cdc_pf.md", "POP_Fatura_Y.md"}
    assert index["POP_Fatura_Y.md"] == ["fatura email"]


def test_strategy_for_doc_precedencia():
    assert strategy_for_doc(DOC_ACESSO) == ("local", 10)
    assert strategy_for_doc("POP_Novo.md") == ("hybrid", 5)
    assert strategy_for_doc("POP_Novo.md", {"POP_Novo.md": ("local", 7)}) == ("local", 7)
    assert strategy_for_doc("d", default=("global", 3)) == ("global", 3)
    settings = BenchmarkSettings(_env_file=None)
    override = settings.routing.strategies  # dict vazio por default
    assert isinstance(override, dict)
    from ragbench.config import DocStrategy

    assert strategy_for_doc("d", {"d": DocStrategy(mode="global", top_k=3)}) == (
        "global",
        3,
    )


def test_route_by_graph_doc_novo_usa_default_ou_override():
    index = {
        "pop_acesso_pf.md": ["senha de 6 digitos"],
        "POP_Fatura_Y.md": ["fatura email codigo de barras"],
    }
    route = route_by_graph("fatura email codigo de barras", index, filled={})
    assert route["doc"] == "POP_Fatura_Y.md"
    assert (route["mode"], route["top_k"]) == ("hybrid", 5)
    route2 = route_by_graph(
        "fatura email codigo de barras",
        index,
        filled={},
        strategies={"POP_Fatura_Y.md": ("local", 8)},
    )
    assert (route2["mode"], route2["top_k"]) == ("local", 8)


def test_extract_slots_generico_e_limite():
    assert extract_slots("abc123", expected_slot="protocolo") == {"protocolo": "abc123"}
    assert extract_slots("x" * 200, expected_slot="obs_livre") == {}
    # Legado preservado mesmo com extra presente.
    assert extract_slots("bloqueio 'U'", expected_slot="protocolo")["codigo_bloqueio"] == "U"


def test_missing_slots_extras_e_pergunta_generica():
    missing = find_missing_slots({"codigo_bloqueio": "U"}, extra_slots=["protocolo"])
    assert "codigo_bloqueio" not in missing
    assert "protocolo" in missing
    assert question_for_slot("protocolo") == "Por favor, informe protocolo?"
    assert "código de bloqueio" in question_for_slot("codigo_bloqueio")


def test_routed_query_preserva_kv_e_adiciona_resumo():
    enriched = build_routed_query("orig?", {"codigo_bloqueio": "U"})
    legacy = build_enriched_query("orig?", {"codigo_bloqueio": "U"})
    assert legacy in enriched  # linha legada intacta como prefixo
    assert "codigo_bloqueio=U" in enriched
    assert "[Resumo para o assistente:" in enriched
    assert build_routed_query("orig?", {}) == "orig?"
    assert "Nenhum dado adicional" in build_routed_instruction({})
    assert "Rota prevista: doc.md" in build_routed_instruction({"a": "b"}, route_doc="doc.md")
    assert clarify_history_turn("q?", "r!") == [
        {"role": "user", "content": "q?"},
        {"role": "assistant", "content": "r!"},
    ]


def test_simulate_classica_com_slots_genericos():
    filled, turns, enriched = simulate_clarification(
        "minha fatura não chegou", {"protocolo": "123", "canal_tentado": "app"}, max_turns=3
    )
    assert filled["protocolo"] == "123"
    assert turns == 2
    assert "protocolo=123" in enriched


def test_guided_full_retorna_historico_e_resumo_com_estrategia():
    index = {
        "pop_acesso_pf.md": ["senha de 6 digitos", "alfa code"],
        "POP_Fatura_Y.md": ["fatura email codigo de barras"],
    }
    filled, turns, enriched, route, history = simulate_clarification_guided_full(
        "fatura email codigo de barras não chegou",
        {"protocolo": "999"},
        entity_index=index,
        max_turns=3,
        strategies={"POP_Fatura_Y.md": ("local", 8)},
    )
    assert turns == 1
    assert filled["protocolo"] == "999"
    assert route["doc"] == "POP_Fatura_Y.md"
    assert (route["mode"], route["top_k"]) == ("local", 8)
    assert "[Resumo para o assistente:" in enriched
    assert len(history) == 2
    assert history[0]["role"] == "user"
    # Assinatura legada continua 4-tupla e com bloco roteado.
    filled2, turns2, enriched2, route2 = simulate_clarification_guided(
        "fatura email codigo de barras não chegou",
        {"protocolo": "999"},
        entity_index=index,
        max_turns=3,
    )
    assert turns2 == 1
    assert filled2["protocolo"] == "999"
    assert "protocolo=999" in enriched2
    assert route2["doc"] == "POP_Fatura_Y.md"


def test_build_llm_messages_sufixo_somente_roteado():
    plain = build_llm_messages("pergunta simples")
    assert ROUTED_SYSTEM_SUFFIX not in plain[0]["content"]
    assert "pt-BR" in plain[0]["content"]
    routed = build_llm_messages("orig?\n[Dados coletados via clarificação: a=b]")
    assert ROUTED_SYSTEM_SUFFIX in routed[0]["content"]


def test_classify_generico_n_docs_e_empate():
    predicted, counts = classify_context_generic("fatura email codigo de barras fatura")
    assert predicted == "POP_Fatura_Envio_Email_anonimizado.md"
    assert counts[predicted] > 0
    predicted2, _ = classify_context_generic(
        "senha de 6 digitos alfa code", docs=["pop_acesso_pf.md", "pop_cdc_pf.md"]
    )
    assert predicted2 == "pop_acesso_pf.md"
    empate, _ = classify_context_generic("xyz nada a ver")
    assert empate == "empate"
    assert "senha" in " ".join(doc_markers_for("pop_acesso_pf.md"))


def test_build_routing_strategies_composta(tmp_path, monkeypatch):
    import os

    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("ROUTING__", "OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__")):
            monkeypatch.delenv(key, raising=False)
    settings = BenchmarkSettings(_env_file=None)
    strategies, default = build_routing_strategies(settings)
    assert strategies[DOC_ACESSO] == ("local", 10)
    assert default == ("hybrid", 5)
    from ragbench.config import DocStrategy

    settings.routing.strategies["POP_Novo.md"] = DocStrategy(mode="global", top_k=3)
    strategies2, _ = build_routing_strategies(settings)
    assert strategies2["POP_Novo.md"] == ("global", 3)
    assert strategy_for_doc("POP_Novo.md", ["nao-tupla"]) == ("hybrid", 5)


def test_extract_nao_confunde_codigo_de_barras():
    """Regressão: 'código de barras' (fatura) não é código de bloqueio."""
    assert "codigo_bloqueio" not in extract_slots("Preciso do código de barras da fatura por email")
    assert extract_slots("bloqueio 'U' no código 8")["codigo_bloqueio"] in {"U", "8"}


def test_rota_final_nao_realimenta_resumo():
    """A rota final sai do texto legado: o Resumo cita o arquivo previsto."""
    index = {
        "pop_acesso_pf.md": ["senha de 6 digitos", "alfa code"],
        "POP_Fatura_Y.md": ["fatura email codigo de barras"],
    }
    filled, turns, enriched, route, _ = simulate_clarification_guided_full(
        "fatura email codigo de barras não chegou",
        {"protocolo": "999"},
        entity_index=index,
        max_turns=3,
    )
    assert "codigo_bloqueio" not in filled
    assert route["doc"] == "POP_Fatura_Y.md"
    assert "Rota prevista: POP_Fatura_Y.md" in enriched


def test_batch_e_router_caminhos_limite(tmp_path):
    """Cobre ramos limite puros (sem turnos, parse direto, scores zerados)."""
    import json

    from ragbench.conversational.batch import load_scenarios
    from ragbench.conversational.router import route_margin, score_docs

    with __import__("pytest").raises(ValueError):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"nao": "lista"}), encoding="utf-8")
        load_scenarios(p)

    # Sem turnos: retorna imediatamente com rota fallback.
    filled, turns, enriched, route, history = simulate_clarification_guided_full(
        "oi", {"protocolo": "1"}, entity_index={}, max_turns=0
    )
    assert turns == 0 and history == [] and enriched == "oi"
    assert route.get("doc") is None

    # Valor parseado direto pelo extrator (sem fallback literal).
    filled2, turns2, _, _, _ = simulate_clarification_guided_full(
        "senha bloqueou",
        {"codigo_bloqueio": "'8'"},
        entity_index={},
        max_turns=3,
    )
    assert filled2["codigo_bloqueio"] == "8" and turns2 == 1

    # Scoring sem tokens válidos e margem com 1 doc.
    index = {"a.md": ["senha"], "b.md": ["cdc"]}
    assert score_docs("de da do", index) == {"a.md": 0.0, "b.md": 0.0}
    assert route_margin({"a.md": 0.5}) == 0.0


def test_classify_legado_cdc_e_fallbacks_curtos():
    from ragbench.cli_commands.probe_cmd import classify_context

    assert classify_context("cdc boleto amortiza")[0] == "pop_cdc_pf.md"
    assert classify_context("xyz")[0] == "empate"
    assert extract_slots("n", expected_slot="tipo_cliente")["tipo_cliente"] == ("não correntista")
    assert (
        extract_slots("sou correntista", expected_slot="tipo_cliente")["tipo_cliente"]
        == "correntista"
    )


def test_merge_run_manifest_caminhos(tmp_path):
    import json

    from ragbench.cli_commands.quota_support import merge_run_manifest

    new = [{"index": 1, "q": "nova"}]
    assert merge_run_manifest(new, tmp_path / "ausente.json") == new

    path = tmp_path / "m.json"
    path.write_text(
        json.dumps([{"index": 0, "q": "antiga"}, {"index": 1, "q": "velha"}, "lixo"]),
        encoding="utf-8",
    )
    merged = merge_run_manifest(new, path)
    assert [m["index"] for m in merged] == [0, 1]
    assert merged[1] == {"index": 1, "q": "nova"}

    path.write_text("{{{invalido", encoding="utf-8")
    assert merge_run_manifest(new, path) == new

    path.write_text(json.dumps([{"sem_index": True}]), encoding="utf-8")
    assert merge_run_manifest(new, path) == new


def test_probe_retrieval_com_fake_engine(monkeypatch, tmp_path):
    """Probe por modo gera JSON+MD sem rede (cobre o fluxo principal)."""

    import json
    import os

    from typer.testing import CliRunner

    from ragbench.cli import app
    from ragbench.cli_commands import deps, probe_cmd
    from ragbench.config import reset_settings_cache

    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__", "CLARIFY__")):
            monkeypatch.delenv(key, raising=False)
    reset_settings_cache()
    settings = BenchmarkSettings(_env_file=None)
    settings.storage_dir = tmp_path / "graph"
    settings.runs_dir = tmp_path / "runs"
    settings.results_dir = tmp_path / "resultados"
    settings.questions_dir = tmp_path / "data"
    settings.questions_dir.mkdir(parents=True)
    monkeypatch.setattr(deps, "get_settings", lambda: settings)

    scenarios = [
        {
            "id": "s1",
            "pergunta_incompleta": "Minha senha bloqueou",
            "slots_simulados": {"codigo_bloqueio": "U"},
            "source_document": "pop_acesso_pf.md",
        }
    ]
    sc_path = settings.questions_dir / "hypothesis_inicial_scenarios.json"
    sc_path.write_text(json.dumps(scenarios), encoding="utf-8")

    class _FakeEngine:
        @classmethod
        def for_chat(cls, settings=None):
            return cls()

        async def initialize(self):
            pass

        async def finalize(self):
            pass

        async def aget_context(self, query, mode=None, top_k=None):
            return "senha de 6 digitos com alfa code e biometria na agencia"

    monkeypatch.setattr(probe_cmd, "LightRAGEngine", _FakeEngine)

    result = CliRunner().invoke(
        app,
        ["probe-retrieval", "--run-name", "probe_t", "--ids", "s1", "--modes", "hybrid"],
    )
    assert result.exit_code == 0, result.output
    out_json = settings.runs_dir / "probe_t" / "retrieval_probe.json"
    rows = json.loads(out_json.read_text(encoding="utf-8"))
    assert rows[0]["doc_previsto"] == "pop_acesso_pf.md"
    assert rows[0]["acertou"] is True
    reset_settings_cache()


def test_run_clarify_reparo_generico_e_historico(monkeypatch, tmp_path):
    """Batch roteado com probe fraca dispara reparo e passa histórico."""

    import json
    import os

    from typer.testing import CliRunner

    from ragbench.cli import app
    from ragbench.cli_commands import deps, run_clarify_cmd

    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__", "CLARIFY__")):
            monkeypatch.delenv(key, raising=False)
    settings = BenchmarkSettings(_env_file=None)
    settings.storage_dir = tmp_path / "graph"
    settings.storage_dir.mkdir(parents=True)
    settings.runs_dir = tmp_path / "runs"
    settings.results_dir = tmp_path / "resultados"
    settings.questions_dir = tmp_path / "data"
    settings.questions_dir.mkdir(parents=True)
    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    monkeypatch.setattr(
        run_clarify_cmd,
        "load_entity_index",
        lambda _d: {
            "pop_acesso_pf.md": ["senha de 6 digitos", "alfa code", "biometria"],
            "pop_cdc_pf.md": ["cdc", "boleto"],
        },
    )

    scenarios = [
        {
            "id": "s1",
            "pergunta_incompleta": "Minha senha bloqueou no site",
            "slots_simulados": {
                "codigo_bloqueio": "U",
                "alfa_code": "não",
                "canal_tentado": "site",
            },
            "ground_truth": "G",
            "tipo": "CONDITIONAL_WORKFLOW",
        }
    ]
    (settings.questions_dir / "hypothesis_inicial_scenarios.json").write_text(
        json.dumps(scenarios), encoding="utf-8"
    )

    seen: dict = {}

    class _FakeEngine:
        llm_model = "fake"

        @classmethod
        def for_chat(cls, settings=None):
            return cls()

        async def initialize(self):
            pass

        async def finalize(self):
            pass

        async def aget_context(self, query, mode=None, top_k=None):
            return "contexto sem nenhum marcador relevante"

        async def aquery(self, query, **kwargs):
            seen["history"] = kwargs.get("history_messages")
            return f"resp:{query[:20]}"

    monkeypatch.setattr(run_clarify_cmd, "LightRAGEngine", _FakeEngine)

    result = CliRunner().invoke(app, ["run-clarify", "--run-name", "routed_rep", "--no-resume"])
    assert result.exit_code == 0, result.output
    manifest = json.loads(
        (settings.runs_dir / "routed_rep" / "clarify_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest[0]["repair_turns"] == 1
    assert manifest[0]["rota_doc"] == "pop_acesso_pf.md"
    assert "[Resumo para o assistente:" in manifest[0]["query_enriquecida"]
    assert manifest[0]["probe_counts"].get("pop_acesso_pf.md") == 0
    assert isinstance(seen["history"], list) and len(seen["history"]) >= 2
