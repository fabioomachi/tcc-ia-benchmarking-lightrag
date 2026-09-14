"""Fase 3: comandos CLI via CliRunner (engines/evaluator fakes, settings em tmp)."""

import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from typer.testing import CliRunner

from ragbench.cli import app
from ragbench.cli_commands import deps, eval_cmd, run_cmd
from ragbench.cli_commands.chat_cmd import apply_chat_model_override
from ragbench.cli_commands.eval_cmd import resolve_eval_db_path
from ragbench.cli_commands.index_cmd import discover_pop_files, seed_default_pops
from ragbench.cli_commands.run_cmd import build_run_id
from ragbench.config import BenchmarkSettings
from ragbench.core.models import GoldenQuestion, QueryExecutionRecord, QuestionType


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


class _FakeHealthClient:
    up = True

    def __init__(self, *args, **kwargs):
        pass

    async def check_health(self) -> bool:
        return type(self).up


class _FakeEngine:
    instances: list["_FakeEngine"] = []
    inserted: list[str] = []

    def __init__(self):
        self.llm_model = "fake-model"
        type(self).instances.append(self)

    @classmethod
    def for_index(cls, settings=None):
        return cls()

    @classmethod
    def for_chat(cls, settings=None):
        return cls()

    async def initialize(self):
        pass

    async def finalize(self):
        pass

    async def ainsert(self, text: str):
        type(self).inserted.append(text)

    async def get_query_embeddings(self, texts: list[str]):
        return np.zeros((len(texts), 3))

    async def aquery(self, query: str, **kwargs):
        return f"resp:{query}"


class _FakeGenerator:
    made: list = []

    def __init__(self, settings=None):
        pass

    async def generate_dataset(self, output_file=None, questions_per_doc: int = 2):
        type(self).made.append((output_file, questions_per_doc))
        return [
            GoldenQuestion(
                question="Q?",
                question_type=QuestionType.EDGE_CASE,
                ground_truth="G",
                source_document="pop.txt",
            )
        ]


class _FakeEvaluator:
    def __init__(self, settings=None):
        pass

    def run_evaluation(self, records, golden_path=None):
        return pd.DataFrame(
            [
                {
                    "faithfulness": 0.9,
                    "answer_relevancy": 0.8,
                    "context_recall": 0.7,
                    "context_precision": 0.6,
                    "question_type": "EDGE_CASE",
                    "question": "Q",
                    "answer": "A",
                    "ground_truth": "G",
                }
            ]
        )


def _reset_fakes():
    _FakeEngine.instances.clear()
    _FakeEngine.inserted.clear()
    _FakeGenerator.made.clear()
    _FakeHealthClient.up = True


def test_health_ok(monkeypatch, tmp_path):
    import ragbench.cli_commands.health as health_mod

    _settings(monkeypatch, tmp_path)
    _reset_fakes()
    monkeypatch.setattr(health_mod, "ResilientOllamaClient", _FakeHealthClient)

    result = CliRunner().invoke(app, ["health"])
    assert result.exit_code == 0, result.output
    assert "operacionais" in result.output


def test_health_failure(monkeypatch, tmp_path):
    import ragbench.cli_commands.health as health_mod

    _settings(monkeypatch, tmp_path)
    _reset_fakes()
    _FakeHealthClient.up = False
    monkeypatch.setattr(health_mod, "ResilientOllamaClient", _FakeHealthClient)

    result = CliRunner().invoke(app, ["health"])
    assert result.exit_code == 1
    assert "Falha no index" in result.output


def test_index_seeds_and_inserts(monkeypatch, tmp_path):
    import ragbench.cli_commands.index_cmd as index_mod

    settings = _settings(monkeypatch, tmp_path)
    _reset_fakes()
    monkeypatch.setattr(index_mod, "LightRAGEngine", _FakeEngine)

    result = CliRunner().invoke(app, ["index", "--no-clean"])
    assert result.exit_code == 0, result.output
    assert len(_FakeEngine.inserted) == 2
    assert all("DOCUMENTO_ORIGEM" in t for t in _FakeEngine.inserted)
    assert (settings.pops_dir / "pop_cancelamento_pix.txt").exists()


def test_generate_dataset(monkeypatch, tmp_path):
    import ragbench.cli_commands.dataset as dataset_mod

    _settings(monkeypatch, tmp_path)  # apenas pelo isolamento via get_settings
    _reset_fakes()
    monkeypatch.setattr(dataset_mod, "GoldenDatasetGenerator", _FakeGenerator)

    out = tmp_path / "golden.json"
    result = CliRunner().invoke(
        app, ["generate-dataset", "--questions-per-doc", "1", "--output", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert "1 perguntas geradas" in result.output
    assert _FakeGenerator.made[0] == (out, 1)


def test_run_benchmark_end_to_end(monkeypatch, tmp_path):
    import ragbench.cli_commands.run_cmd as run_mod

    settings = _settings(monkeypatch, tmp_path)
    _reset_fakes()
    monkeypatch.setattr(run_mod, "LightRAGEngine", _FakeEngine)
    settings.questions_dir.mkdir(parents=True)
    (settings.questions_dir / "qs.txt").write_text("pergunta um\npergunta dois\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["run", "--run-name", "t1", "--no-resume"])
    assert result.exit_code == 0, result.output

    run_dir = settings.runs_dir / "t1"
    assert (run_dir / "checkpoint.sqlite3").exists()
    assert (run_dir / "benchmark_analise_detalhada.csv").exists()
    assert (run_dir / "resumo_benchmark.md").exists()
    assert (settings.results_dir / "benchmark_analise_detalhada.csv").exists()
    assert (settings.results_dir / "resumo_benchmark.md").exists()


def test_run_no_queries(monkeypatch, tmp_path):
    settings = _settings(monkeypatch, tmp_path)
    settings.questions_dir.mkdir(parents=True)

    result = CliRunner().invoke(app, ["run", "--run-name", "vazia"])
    assert result.exit_code == 0, result.output
    assert "Nenhuma pergunta encontrada" in result.output


def test_eval_run_id(monkeypatch, tmp_path):
    import ragbench.cli_commands.eval_cmd as eval_mod

    settings = _settings(monkeypatch, tmp_path)
    monkeypatch.setattr(eval_mod, "RagasEvaluator", _FakeEvaluator)

    from ragbench.infrastructure.storage import SQLiteExecutionStorage

    run_dir = settings.runs_dir / "r1"
    run_dir.mkdir(parents=True)
    SQLiteExecutionStorage(run_dir / "checkpoint.sqlite3").save_record(
        QueryExecutionRecord(index=0, query="q", response="r")
    )

    result = CliRunner().invoke(app, ["eval", "--run-id", "r1"])
    assert result.exit_code == 0, result.output
    assert (run_dir / "ragas_evaluation_results.csv").exists()
    assert (run_dir / "resumo_qualidade_ragas.md").exists()
    assert (settings.results_dir / "ragas_evaluation_results.csv").exists()


def test_eval_no_checkpoint(monkeypatch, tmp_path):
    settings = _settings(monkeypatch, tmp_path)
    settings.runs_dir.mkdir(parents=True)

    result = CliRunner().invoke(app, ["eval"])
    assert result.exit_code == 1
    assert "Nenhum checkpoint" in result.output


def test_build_run_id():
    assert build_run_id("minha-run", "hybrid", datetime(2026, 1, 2, 3, 4, 5)) == "minha-run"
    assert build_run_id(None, "local", datetime(2026, 1, 2, 3, 4, 5)) == "run_20260102_030405_local"


def test_resolve_eval_db_path(tmp_path):
    explicit = tmp_path / "c.sqlite3"
    assert resolve_eval_db_path(tmp_path, None, explicit) == explicit
    assert resolve_eval_db_path(tmp_path, "r9", None) == tmp_path / "r9" / "checkpoint.sqlite3"

    import time

    (tmp_path / "old").mkdir()
    (tmp_path / "new").mkdir()
    old_ckpt = tmp_path / "old" / "checkpoint.sqlite3"
    new_ckpt = tmp_path / "new" / "checkpoint.sqlite3"
    old_ckpt.write_text("a")
    new_ckpt.write_text("b")
    # Garante mtimes distintos para ordenação determinística
    os.utime(old_ckpt, (1000000000, 1000000000))
    os.utime(new_ckpt, (1000000000 + 100, 1000000000 + 100))
    time.sleep(0.01)
    assert resolve_eval_db_path(tmp_path, None, None) == new_ckpt

    try:
        resolve_eval_db_path(tmp_path / "vazia", None, None)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("deveria levantar FileNotFoundError")


def test_resolve_eval_db_path_missing_dir():
    import pytest as _pytest

    with _pytest.raises(FileNotFoundError):
        resolve_eval_db_path(Path("/nao/existe"), None, None)


def test_apply_chat_model_override_copies(monkeypatch, tmp_path):
    settings = _settings(monkeypatch, tmp_path)
    original_model = settings.chat.llm_model

    same = apply_chat_model_override(settings, None)
    assert same is settings

    overridden = apply_chat_model_override(settings, "outro-modelo")
    assert overridden is not settings
    assert overridden.chat.llm_model == "outro-modelo"
    assert settings.chat.llm_model == original_model  # global intacto


def test_discover_and_seed_pops(tmp_path):
    d = tmp_path / "pops"
    d.mkdir()
    assert discover_pop_files(d) == []
    (d / "a.txt").write_text("x", encoding="utf-8")
    assert [p.name for p in discover_pop_files(d)] == ["a.txt"]

    d2 = tmp_path / "pops2"
    d2.mkdir()
    seeded = seed_default_pops(d2)
    assert len(seeded) == 2
    assert {p.name for p in seeded} == {"pop_cancelamento_pix.txt", "pop_bloqueio_cartao.txt"}


def test_run_and_eval_helpers_importable():
    assert callable(run_cmd.build_run_id)
    assert callable(eval_cmd.resolve_eval_db_path)
