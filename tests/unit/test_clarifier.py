"""Spike hipótese: clarificação por slots antes do grafo."""

from ragbench.cli_commands.clarify_cmd import collect_slots_interactive
from ragbench.conversational.clarifier import (
    build_enriched_query,
    extract_slots,
    find_missing_slots,
    merge_slots,
    next_clarifying_question,
    should_ask_more,
)


def test_extract_bloqueio_u():
    slots = extract_slots("senha 6 dígitos com bloqueio 'U'")
    assert slots["codigo_bloqueio"] == "U"


def test_extract_nao_captura_letra_de_bloqueio_pelo():
    # Regressão: "bloqueio pelo site" capturava P como codigo_bloqueio.
    slots = extract_slots("Minha senha bloqueou, como desbloqueio pelo site?")
    assert "codigo_bloqueio" not in slots
    assert slots.get("canal_tentado") == "site"


def test_extract_sem_alfa_e_biometria():
    slots = extract_slots("sem Alfa Code, biometria há 5 dias, tentando pelo site")
    assert slots["alfa_code"] == "não"
    assert slots["biometria_dias"] == "5"
    assert slots["canal_tentado"] == "site"


def test_extract_tipo_cliente():
    assert extract_slots("sou correntista")["tipo_cliente"] == "correntista"
    assert extract_slots("não sou correntista")["tipo_cliente"] == "não correntista"


def test_missing_e_next_question():
    filled = {"codigo_bloqueio": "U"}
    missing = find_missing_slots(filled)
    assert "codigo_bloqueio" not in missing
    assert "alfa_code" in missing
    assert next_clarifying_question(missing) is not None
    assert next_clarifying_question([]) is None


def test_should_ask_more():
    assert should_ask_more(["alfa_code"], 0, 3) is True
    assert should_ask_more(["alfa_code"], 3, 3) is False
    assert should_ask_more([], 0, 3) is False


def test_merge_e_enriched_query():
    merged = merge_slots({"a": "1"}, {"b": "2"})
    assert merged == {"a": "1", "b": "2"}
    q = build_enriched_query("como desbloqueio?", {"codigo_bloqueio": "U"})
    assert "codigo_bloqueio=U" in q
    assert build_enriched_query("x", {}) == "x"


def test_collect_slots_interactive_simulado():
    answers = iter(["U", "não", "5 dias"])
    filled, turns, _route = collect_slots_interactive(
        "minha senha bloqueou",
        console_input=lambda _p: next(answers),
        console_print=lambda _m: None,
        max_turns=3,
    )
    assert turns == 3
    assert filled.get("codigo_bloqueio") == "U"
    assert filled.get("biometria_dias") == "5"


def test_collect_respeita_max_turns():
    filled, turns, _route = collect_slots_interactive(
        "oi",
        console_input=lambda _p: "resposta vaga sem slots",
        console_print=lambda _m: None,
        max_turns=2,
    )
    assert turns == 2
    assert isinstance(filled, dict)


def test_clarify_settings_default(tmp_path, monkeypatch):
    import os

    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("CLARIFY__", "OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__")):
            monkeypatch.delenv(key, raising=False)
    from ragbench.config import BenchmarkSettings

    settings = BenchmarkSettings(_env_file=None)
    assert settings.clarify.max_turns == 3
