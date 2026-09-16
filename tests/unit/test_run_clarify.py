"""Batch da hipótese: simulação + run-clarify com fake engine."""

import json

from typer.testing import CliRunner

from ragbench.cli import app
from ragbench.conversational.batch import load_scenarios, simulate_clarification


def test_simulate_preenche_slots_e_respeita_max(tmp_path):
    scenarios = [
        {
            "pergunta_incompleta": "Minha senha bloqueou",
            "slots_simulados": {"codigo_bloqueio": "U", "alfa_code": "não"},
        }
    ]
    path = tmp_path / "sc.json"
    path.write_text(json.dumps(scenarios), encoding="utf-8")
    items = load_scenarios(path)
    assert len(items) == 1

    filled, turns, enriched = simulate_clarification(
        "Minha senha bloqueou", {"codigo_bloqueio": "U", "alfa_code": "não"}, max_turns=1
    )
    assert turns == 1
    assert "codigo_bloqueio=U" in enriched
    assert filled["codigo_bloqueio"] == "U"

    filled2, turns2, _ = simulate_clarification(
        "Minha senha bloqueou", {"codigo_bloqueio": "U", "alfa_code": "não"}, max_turns=5
    )
    assert turns2 >= 2


def test_simulate_sem_valor_para():
    filled, turns, enriched = simulate_clarification("oi", {}, max_turns=3)
    assert turns == 0
    assert enriched == "oi"
    assert filled == {}


def test_simulate_pula_slots_sem_valor():
    # Regressão: cenário CDC só tem tipo_cliente/canal; não deve travar em 0.
    filled, turns, enriched = simulate_clarification(
        "Quero cancelar meu CDC renovação, como faço?",
        {"tipo_cliente": "correntista", "canal_tentado": "app"},
        max_turns=3,
    )
    assert turns == 2
    assert filled["tipo_cliente"] == "correntista"
    assert filled["canal_tentado"] == "app"
    assert "tipo_cliente=correntista" in enriched


def test_run_clarify_gera_mesmos_artefatos_do_run(monkeypatch, tmp_path):
    import os

    from ragbench.cli_commands import deps, run_clarify_cmd
    from ragbench.config import BenchmarkSettings

    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__", "CLARIFY__")):
            monkeypatch.delenv(key, raising=False)
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
            "ground_truth": "G",
            "tipo": "CONDITIONAL_WORKFLOW",
        }
    ]
    sc_path = settings.questions_dir / "hypothesis_inicial_scenarios.json"
    sc_path.write_text(json.dumps(scenarios), encoding="utf-8")

    class _FakeEngine:
        llm_model = "fake"

        @classmethod
        def for_chat(cls, settings=None):
            return cls()

        async def initialize(self):
            pass

        async def finalize(self):
            pass

        async def aquery(self, query, **kwargs):
            return f"resp:{query[:20]}"

    monkeypatch.setattr(run_clarify_cmd, "LightRAGEngine", _FakeEngine)

    result = CliRunner().invoke(app, ["run-clarify", "--run-name", "clarify_t1", "--no-resume"])
    assert result.exit_code == 0, result.output

    run_dir = settings.runs_dir / "clarify_t1"
    assert (run_dir / "checkpoint.sqlite3").exists()
    assert (run_dir / "benchmark_analise_detalhada.csv").exists()
    assert (run_dir / "resumo_benchmark.md").exists()
    assert (run_dir / "clarify_manifest.json").exists()
    manifest = json.loads((run_dir / "clarify_manifest.json").read_text(encoding="utf-8"))
    assert manifest[0]["clarify_turns"] >= 1
    assert "codigo_bloqueio=U" in manifest[0]["query_enriquecida"]
    # mesmo padrão do run: cópia em resultados/
    assert (settings.results_dir / "benchmark_analise_detalhada.csv").exists()


def test_run_clarify_help():
    result = CliRunner().invoke(app, ["run-clarify", "--help"])
    assert result.exit_code == 0
    assert "cenários" in result.output.lower() or "cenarios" in result.output.lower()
