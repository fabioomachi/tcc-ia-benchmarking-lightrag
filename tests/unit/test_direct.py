"""Baseline LLM-direto: sem grafo, sem retrieval, mesmo modelo do chat."""

import json

import numpy as np
from typer.testing import CliRunner

from ragbench.cli import app
from ragbench.core.models import QueryInteractionSource, SearchMode
from ragbench.engines.direct_llm_engine import DIRECT_SYSTEM_PROMPT, DirectLLMEngine


class _FakeOllama:
    def __init__(self, settings=None):
        self.calls: list = []

    async def generate_completion(self, model, messages, **kwargs):
        self.calls.append({"model": model, "messages": messages})
        return "resposta direta"

    async def get_embeddings(self, model, texts, **kwargs):
        return np.zeros((len(texts), 3))


def _settings(monkeypatch, tmp_path):
    import os

    from ragbench.cli_commands import deps
    from ragbench.config import BenchmarkSettings

    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__", "ROUTING__")):
            monkeypatch.delenv(key, raising=False)
    settings = BenchmarkSettings(_env_file=None)
    settings.chat.llm_model = "gemini-fake"
    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    return settings


async def _collect(coro):
    return await coro


def test_usa_modelo_do_chat():
    import asyncio

    async def _run():
        from ragbench.config import BenchmarkSettings

        settings = BenchmarkSettings(_env_file=None)
        engine = DirectLLMEngine(settings=settings, ollama_client=_FakeOllama())
        assert engine.llm_model == settings.chat.llm_model

    asyncio.run(_run())


def test_aquery_sem_contexto_recuperado():
    import asyncio

    async def _run():
        from ragbench.config import BenchmarkSettings

        fake = _FakeOllama()
        engine = DirectLLMEngine(settings=BenchmarkSettings(_env_file=None), ollama_client=fake)
        resp = await engine.aquery("o que é bloqueio U?")
        assert resp == "resposta direta"
        messages = fake.calls[0]["messages"]
        full = " ".join(m["content"] for m in messages).lower()
        assert "bloqueio u" in full
        assert "sem acesso" in full or "sem contexto" in full or "conhecimento geral" in full
        # Nenhum chunk/contexto do grafo é injetado
        assert "chunk" not in full

    asyncio.run(_run())


def test_lifecycle_noop_e_ainsert_avisa():
    import asyncio

    async def _run():
        from ragbench.config import BenchmarkSettings

        engine = DirectLLMEngine(
            settings=BenchmarkSettings(_env_file=None), ollama_client=_FakeOllama()
        )
        await engine.initialize()
        await engine.ainsert("doc qualquer")
        await engine.finalize()

    asyncio.run(_run())


def test_system_prompt_ptbr():
    assert "pt-BR" in DIRECT_SYSTEM_PROMPT or "Português" in DIRECT_SYSTEM_PROMPT


def test_run_direct_gera_artefatos_com_baseline_engine(monkeypatch, tmp_path):
    import os

    from ragbench.cli_commands import deps, run_direct_cmd
    from ragbench.config import BenchmarkSettings
    from ragbench.infrastructure.storage import SQLiteExecutionStorage

    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__", "ROUTING__")):
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
            "pergunta_incompleta": "Senha bloqueou?",
            "pergunta_completa": "Senha 6 dígitos bloqueio U, como resolver?",
            "slots_simulados": {},
            "ground_truth": "G",
            "tipo": "EDGE_CASE",
            "source_document": "pop_acesso_pf.md",
        }
    ]
    sc_path = settings.questions_dir / "hypothesis_inicial_scenarios.json"
    sc_path.write_text(json.dumps(scenarios), encoding="utf-8")

    class _FakeEngine:
        llm_model = "fake"

        def __init__(self, settings=None):
            pass

        async def initialize(self):
            pass

        async def finalize(self):
            pass

        async def aquery(self, query, **kwargs):
            return f"resp:{query[:10]}"

    monkeypatch.setattr(run_direct_cmd, "DirectLLMEngine", _FakeEngine)

    result = CliRunner().invoke(app, ["run-direct", "--input", "completa", "--run-name", "d1"])
    assert result.exit_code == 0, result.output

    run_dir = settings.runs_dir / "d1"
    assert (run_dir / "checkpoint.sqlite3").exists()
    assert (run_dir / "benchmark_analise_detalhada.csv").exists()
    assert (run_dir / "golden.json").exists()
    records = SQLiteExecutionStorage(run_dir / "checkpoint.sqlite3").load_all_records()
    assert records[0].mode == SearchMode.DIRECT
    assert records[0].source == QueryInteractionSource.BASELINE_ENGINE
    golden = json.loads((run_dir / "golden.json").read_text(encoding="utf-8"))
    assert golden[0]["question"] == "Senha 6 dígitos bloqueio U, como resolver?"


def test_run_direct_rejeita_input_invalido(monkeypatch, tmp_path):
    _settings(monkeypatch, tmp_path)
    result = CliRunner().invoke(app, ["run-direct", "--input", "x"])
    assert result.exit_code == 1
