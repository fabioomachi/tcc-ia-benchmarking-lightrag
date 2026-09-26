"""Parada graciosa por cota (429) nos lotes de benchmark com retomada."""

import json
import os

import numpy as np
import pytest
from typer.testing import CliRunner

from ragbench.cli import app
from ragbench.cli_commands import deps
from ragbench.cli_commands.quota_support import QUOTA_EXIT_CODE
from ragbench.config import BenchmarkSettings
from ragbench.core.exceptions import QuotaExhaustedError
from ragbench.core.models import RagExecutionStatus
from ragbench.infrastructure.semantic_cache import SemanticCache
from ragbench.infrastructure.storage import SQLiteExecutionStorage
from ragbench.runner import BenchmarkRunner


def _settings(monkeypatch, tmp_path) -> BenchmarkSettings:
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__")):
            monkeypatch.delenv(key, raising=False)
    settings = BenchmarkSettings(_env_file=None)
    settings.pops_dir = tmp_path / "pops"
    settings.questions_dir = tmp_path / "questions"
    settings.storage_dir = tmp_path / "graph"
    settings.runs_dir = tmp_path / "runs"
    settings.results_dir = tmp_path / "resultados"
    settings.chat.llm_model = "gemini-fake"
    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    return settings


class _QuotaEngine:
    """Fake que estoura a quota numa query específica (match por conteúdo)."""

    def __init__(self, quota_on: str = "Q2"):
        self.llm_model = "fake-model"
        self.calls: list[str] = []
        self.quota_on = quota_on

    async def initialize(self):
        pass

    async def finalize(self):
        pass

    async def get_query_embeddings(self, texts: list[str]) -> np.ndarray:
        # One-hot por query para nunca acertar o cache semântico entre queries.
        vecs = []
        for t in texts:
            vec = [0.0, 0.0, 0.0, 0.0]
            try:
                vec[int(t.strip()[-1]) % 4] = 1.0
            except (ValueError, IndexError):
                vec[0] = 1.0
            vecs.append(vec)
        return np.array(vecs)

    async def aquery(self, query: str, **kwargs) -> str:
        self.calls.append(query)
        if self.quota_on and self.quota_on in query:
            raise QuotaExhaustedError("Cota da API esgotada no modelo fake.")
        return f"resp:{query}"


class _EmbedQuotaEngine(_QuotaEngine):
    async def get_query_embeddings(self, texts: list[str]) -> np.ndarray:
        raise QuotaExhaustedError("Cota de embeddings esgotada.")


def _make_runner(tmp_path, engine) -> BenchmarkRunner:
    storage = SQLiteExecutionStorage(tmp_path / "ckpt.sqlite3")
    settings = BenchmarkSettings(_env_file=None)
    return BenchmarkRunner(
        engine=engine,  # type: ignore[arg-type]
        storage=storage,
        cache=SemanticCache(threshold=0.99),
        settings=settings,
    )


@pytest.mark.asyncio
async def test_runner_aborts_batch_on_quota(tmp_path):
    engine = _QuotaEngine(quota_on="Q2")
    runner = _make_runner(tmp_path, engine)
    with pytest.raises(QuotaExhaustedError):
        await runner.execute_batch(
            queries=["Q1", "Q2", "Q3", "Q4"], concurrency=1, resume=False, show_progress=False
        )
    # Q3/Q4 nunca tentadas; Q2 gravada como ERROR retomável; Q1 sucesso.
    assert engine.calls == ["Q1", "Q2"]
    completed = runner.storage.get_completed_indices()
    assert completed == {0}
    all_recs = {r.index: r for r in runner.storage.load_all_records()}
    assert set(all_recs) == {0, 1}
    assert all_recs[1].status == RagExecutionStatus.ERROR
    assert "QuotaExhaustedError" in (all_recs[1].error_message or "")


@pytest.mark.asyncio
async def test_runner_quota_in_embeddings_is_not_swallowed(tmp_path):
    engine = _EmbedQuotaEngine(quota_on=None)
    runner = _make_runner(tmp_path, engine)
    with pytest.raises(QuotaExhaustedError):
        await runner.execute_batch(queries=["Q1"], concurrency=1, resume=False, show_progress=False)
    # Nada gravado como sucesso; bypass de cache não mascarou a quota.
    assert runner.storage.get_completed_indices() == set()


@pytest.mark.asyncio
async def test_runner_resume_after_quota_completes(tmp_path):
    engine = _QuotaEngine(quota_on="Q2")
    runner = _make_runner(tmp_path, engine)
    with pytest.raises(QuotaExhaustedError):
        await runner.execute_batch(
            queries=["Q1", "Q2", "Q3"], concurrency=1, resume=False, show_progress=False
        )
    engine.quota_on = None  # dia seguinte: cota renovada
    records = await runner.execute_batch(
        queries=["Q1", "Q2", "Q3"], concurrency=1, resume=True, show_progress=False
    )
    by_index = {r.index: r for r in records}
    assert set(by_index) == {0, 1, 2}
    assert all(r.status == RagExecutionStatus.SUCCESS for r in by_index.values())
    assert engine.calls == ["Q1", "Q2", "Q2", "Q3"]  # Q1 não repetida


def _write_questions(path, questions: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(questions) + "\n", encoding="utf-8")


def test_run_cli_quota_exit_3_and_resume(monkeypatch, tmp_path):
    import ragbench.cli_commands.run_cmd as run_mod

    settings = _settings(monkeypatch, tmp_path)
    engine = _QuotaEngine(quota_on="Q2")
    monkeypatch.setattr(run_mod, "LightRAGEngine", _FakeEngineFactory(engine))
    questions_file = settings.questions_dir / "qs.txt"
    _write_questions(questions_file, ["Q1", "Q2", "Q3"])

    result = CliRunner().invoke(
        app, ["run", "--run-name", "quota1", "--target", str(questions_file), "--concurrency", "1"]
    )
    assert result.exit_code == QUOTA_EXIT_CODE, result.output
    assert "Retome" in result.output and "quota1" in result.output
    run_dir = settings.runs_dir / "quota1"
    assert (run_dir / "checkpoint.sqlite3").exists()
    assert (run_dir / "benchmark_analise_detalhada.csv").exists()  # parcial exportado
    assert (run_dir / "resumo_benchmark.md").exists()

    engine.quota_on = None  # dia seguinte
    result2 = CliRunner().invoke(
        app, ["run", "--run-name", "quota1", "--target", str(questions_file), "--concurrency", "1"]
    )
    assert result2.exit_code == 0, result2.output
    assert engine.calls == ["Q1", "Q2", "Q2", "Q3"]


class _FakeEngineFactory:
    """for_index/for_chat retornando a instância compartilhada."""

    def __init__(self, instance):
        self.instance = instance

    def __call__(self, *args, **kwargs):
        return self

    def for_index(self, settings=None):
        return self.instance

    def for_chat(self, settings=None):
        return self.instance


def _write_scenarios(path, n: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    items = [
        {
            "id": f"s{i}",
            "pergunta_completa": f"QC{i}",
            "pergunta_incompleta": f"QI{i}",
            "slots_simulados": {},
            "ground_truth": f"G{i}",
            "tipo": "EDGE_CASE",
        }
        for i in range(n)
    ]
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")


class _QuotaDirectEngine:
    def __init__(self, quota_on: str | None = "QC1"):
        self.llm_model = "fake-direct"
        self.calls: list[str] = []
        self.quota_on = quota_on

    async def initialize(self):
        pass

    async def finalize(self):
        pass

    async def aquery(self, query: str, **kwargs) -> str:
        self.calls.append(query)
        if self.quota_on and self.quota_on in query:
            raise QuotaExhaustedError("quota direct")
        return f"resp:{query}"


def test_run_direct_quota_exit_3(monkeypatch, tmp_path):
    import ragbench.cli_commands.run_direct_cmd as direct_mod

    settings = _settings(monkeypatch, tmp_path)
    engine = _QuotaDirectEngine()
    monkeypatch.setattr(direct_mod, "DirectLLMEngine", lambda settings=None: engine)
    scenarios = settings.questions_dir / "sc.json"
    _write_scenarios(scenarios, 3)

    result = CliRunner().invoke(
        app, ["run-direct", "--run-name", "qd1", "--scenarios", str(scenarios)]
    )
    assert result.exit_code == QUOTA_EXIT_CODE, result.output
    assert "qd1" in result.output
    run_dir = settings.runs_dir / "qd1"  # build_run_id devolve o nome dado
    assert (run_dir / "checkpoint.sqlite3").exists()
    assert (run_dir / "benchmark_analise_detalhada.csv").exists()  # parcial
    assert any("QC1" in c for c in engine.calls)  # cenário da quota tentado
    from ragbench.infrastructure.storage import SQLiteExecutionStorage as _S

    recs = {r.index: r for r in _S(run_dir / "checkpoint.sqlite3").load_all_records()}
    assert recs[0].status == RagExecutionStatus.SUCCESS
    assert recs[1].status == RagExecutionStatus.ERROR
    assert "QuotaExhaustedError" in (recs[1].error_message or "")
    # Cenário 2: ou nunca tentado (cancelado) ou concluído antes do aborto —
    # ambos estados consistentes; nunca fica meio-gravado como sucesso falso.
    assert 2 not in recs or recs[2].status == RagExecutionStatus.SUCCESS


class _QuotaClarifyEngine(_QuotaDirectEngine):
    async def aget_context(self, query: str, **kwargs) -> str:
        return ""


def test_run_clarify_quota_exit_3(monkeypatch, tmp_path):
    import ragbench.cli_commands.run_clarify_cmd as clarify_mod

    settings = _settings(monkeypatch, tmp_path)
    engine = _QuotaClarifyEngine(quota_on="QI1")
    monkeypatch.setattr(clarify_mod, "LightRAGEngine", _FakeEngineFactory(engine))
    scenarios = settings.questions_dir / "sc.json"
    _write_scenarios(scenarios, 3)

    result = CliRunner().invoke(
        app, ["run-clarify", "--run-name", "qc1", "--scenarios", str(scenarios)]
    )
    assert result.exit_code == QUOTA_EXIT_CODE, result.output
    assert "qc1" in result.output
    # Sequencial: QI0 ok, QI1 quota, QI2 nunca tentado.
    assert not any("QI2" in c for c in engine.calls)
    from ragbench.infrastructure.storage import SQLiteExecutionStorage

    run_dir = settings.runs_dir / "qc1"  # build_run_id devolve o nome dado
    recs = {
        r.index: r
        for r in SQLiteExecutionStorage(run_dir / "checkpoint.sqlite3").load_all_records()
    }
    assert recs[0].status == RagExecutionStatus.SUCCESS
    assert recs[1].status == RagExecutionStatus.ERROR
    assert 2 not in recs
