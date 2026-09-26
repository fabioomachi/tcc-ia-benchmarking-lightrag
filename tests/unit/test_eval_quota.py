"""Parada graciosa por cota (429) no `eval` RAGAS: probe, gate 100% NaN, exit 3."""

import json
import os

import httpx
import pandas as pd
import pytest
from openai import RateLimitError
from typer.testing import CliRunner

from ragbench.cli import app
from ragbench.cli_commands import deps
from ragbench.cli_commands.quota_support import QUOTA_EXIT_CODE
from ragbench.config import BenchmarkSettings
from ragbench.core.exceptions import OllamaConnectionError, QuotaExhaustedError
from ragbench.core.models import QueryExecutionRecord
from ragbench.evaluation.ragas_evaluator import GeminiRestEmbeddings, RagasEvaluator
from ragbench.infrastructure.storage import SQLiteExecutionStorage


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
    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    return settings


def _rate_limit_error() -> RateLimitError:
    response = httpx.Response(429, request=httpx.Request("POST", "http://fake"))
    return RateLimitError("429 quota exceeded", response=response, body=None)


class _HealthyEmbeddings:
    def embed_query(self, text: str):
        return [0.1] * 4


class _HealthyLLM:
    def invoke(self, prompt: str):
        return "OK"


class _QuotaEmbeddings:
    def embed_query(self, text: str):
        raise QuotaExhaustedError("sem cota")


class _RateLimitLLM:
    def invoke(self, prompt: str):
        raise _rate_limit_error()


class _BrokenEmbeddings:
    def embed_query(self, text: str):
        raise RuntimeError("auth quebrou")


def _evaluator(**factories) -> RagasEvaluator:
    settings = BenchmarkSettings(_env_file=None)
    return RagasEvaluator(
        settings=settings,
        judge_llm_factory=factories.get("llm", _HealthyLLM),
        embeddings_factory=factories.get("emb", _HealthyEmbeddings),
    )


def test_probe_quota_healthy():
    assert _evaluator().probe_quota() is True


def test_probe_quota_false_on_embeddings_quota():
    assert _evaluator(emb=_QuotaEmbeddings).probe_quota() is False


def test_probe_quota_false_on_judge_rate_limit():
    assert _evaluator(llm=_RateLimitLLM).probe_quota() is False


def test_probe_quota_propagates_non_quota_error():
    with pytest.raises(RuntimeError, match="auth quebrou"):
        _evaluator(emb=_BrokenEmbeddings).probe_quota()


class _Resp:
    def __init__(self, status_code: int):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code != 200:
            raise httpx.HTTPStatusError("boom", request=None, response=None)  # type: ignore[arg-type]

    def json(self):
        return {"embedding": {"values": [0.2] * 4}}


class _FakeHttpxClient:
    def __init__(self, status_code: int):
        self.status_code = status_code

    def post(self, *args, **kwargs):
        return _Resp(self.status_code)


def test_gemini_embeddings_persistent_429_raises_quota(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *a, **k: None)
    emb = GeminiRestEmbeddings(
        api_key="k", api_base_url="http://fake", model="m", dim=4, max_attempts=2
    )
    with pytest.raises(QuotaExhaustedError):
        emb._embed_one(_FakeHttpxClient(429), "oi")


def test_gemini_embeddings_non_429_keeps_connection_error(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *a, **k: None)
    emb = GeminiRestEmbeddings(
        api_key="k", api_base_url="http://fake", model="m", dim=4, max_attempts=2
    )
    with pytest.raises(OllamaConnectionError):
        emb._embed_one(_FakeHttpxClient(500), "oi")


def _records_and_golden(tmp_path):
    recs = [QueryExecutionRecord(index=0, query="Q?", response="R")]
    golden = tmp_path / "golden.json"
    golden.write_text(
        json.dumps(
            [
                {
                    "question": "Q?",
                    "question_type": "EDGE_CASE",
                    "ground_truth": "G",
                    "source_document": "",
                }
            ]
        ),
        encoding="utf-8",
    )
    return recs, golden


class _FakeRagasResult:
    def __init__(self, df: pd.DataFrame):
        self._df = df

    def to_pandas(self):
        return self._df


def _all_nan_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "faithfulness": float("nan"),
                "answer_relevancy": float("nan"),
                "context_recall": float("nan"),
                "context_precision": float("nan"),
            }
        ]
    )


def test_run_evaluation_all_nan_raises_quota(tmp_path):
    recs, golden = _records_and_golden(tmp_path)
    evaluator = _evaluator()
    evaluator._evaluate_fn = lambda **kwargs: _FakeRagasResult(_all_nan_df())  # type: ignore[method-assign]
    with pytest.raises(QuotaExhaustedError, match="100% NaN"):
        evaluator.run_evaluation(recs, golden_path=golden)


def test_run_evaluation_partial_nan_returns_df(tmp_path):
    recs, golden = _records_and_golden(tmp_path)
    df = pd.concat(
        [
            pd.DataFrame(
                [
                    {
                        "faithfulness": 0.9,
                        "answer_relevancy": 0.8,
                        "context_recall": 0.7,
                        "context_precision": 0.6,
                    }
                ]
            ),
            _all_nan_df(),
        ],
        ignore_index=True,
    )
    evaluator = _evaluator()
    evaluator._evaluate_fn = lambda **kwargs: _FakeRagasResult(df)  # type: ignore[method-assign]
    out = evaluator.run_evaluation(recs, golden_path=golden)
    assert len(out) == 2


class _ProbeFailEvaluator:
    def __init__(self, settings=None):
        pass

    def probe_quota(self):
        return False

    def run_evaluation(self, records, golden_path=None):
        raise AssertionError("não deveria avaliar com probe False")


class _AllNanEvaluator:
    def __init__(self, settings=None):
        pass

    def probe_quota(self):
        return True

    def run_evaluation(self, records, golden_path=None):
        raise QuotaExhaustedError("100% NaN (fake)")


def _seed_checkpoint(settings: BenchmarkSettings, run_id: str = "r1") -> None:
    run_dir = settings.runs_dir / run_id
    run_dir.mkdir(parents=True)
    SQLiteExecutionStorage(run_dir / "checkpoint.sqlite3").save_record(
        QueryExecutionRecord(index=0, query="q", response="r")
    )


def test_eval_cli_probe_fail_exit_3_no_files(monkeypatch, tmp_path):
    import ragbench.cli_commands.eval_cmd as eval_mod

    settings = _settings(monkeypatch, tmp_path)
    monkeypatch.setattr(eval_mod, "RagasEvaluator", _ProbeFailEvaluator)
    _seed_checkpoint(settings)

    result = CliRunner().invoke(app, ["eval", "--run-id", "r1"])
    assert result.exit_code == QUOTA_EXIT_CODE, result.output
    assert "eval --run-id r1" in result.output
    assert not (settings.runs_dir / "r1" / "ragas_evaluation_results.csv").exists()


def test_eval_cli_all_nan_preserves_previous_csv(monkeypatch, tmp_path):
    import ragbench.cli_commands.eval_cmd as eval_mod

    settings = _settings(monkeypatch, tmp_path)
    monkeypatch.setattr(eval_mod, "RagasEvaluator", _AllNanEvaluator)
    _seed_checkpoint(settings)
    previous = settings.runs_dir / "r1" / "ragas_evaluation_results.csv"
    previous.write_text("conteudo-bom-anterior", encoding="utf-8")

    result = CliRunner().invoke(app, ["eval", "--run-id", "r1"])
    assert result.exit_code == QUOTA_EXIT_CODE, result.output
    assert previous.read_text(encoding="utf-8") == "conteudo-bom-anterior"
