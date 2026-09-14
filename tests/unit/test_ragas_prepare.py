"""Fase 2: RagasEvaluator sem LLM real (factories + evaluate_fn injetados)."""

import json
import os

import pandas as pd
import pytest

from ragbench.config import BenchmarkSettings
from ragbench.core.exceptions import EvaluationError
from ragbench.core.models import QueryExecutionRecord, RagExecutionStatus
from ragbench.evaluation.ragas_evaluator import (
    RagasEvaluator,
    select_relevancy_metric,
)


def _hermetic_settings(monkeypatch, tmp_path) -> BenchmarkSettings:
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__")):
            monkeypatch.delenv(key, raising=False)
    return BenchmarkSettings(_env_file=None)


def _rec(query: str, response: str | None = "resp", **overrides) -> QueryExecutionRecord:
    base = {"query": query, "response": response, "status": RagExecutionStatus.SUCCESS}
    base.update(overrides)
    return QueryExecutionRecord(**base)


def _golden_file(tmp_path, items: list[dict]):
    path = tmp_path / "golden.json"
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return path


def test_normalize_and_is_gemini():
    assert RagasEvaluator._normalize_text("  Olá   MUNDO ") == "olá mundo"
    assert RagasEvaluator._normalize_text("") == ""
    assert RagasEvaluator._is_gemini_model("gemini-3.8-flash") is True
    assert RagasEvaluator._is_gemini_model("qwen2.5:7b") is False


def test_select_relevancy_metric_by_transport():
    gemini_metric = select_relevancy_metric("gemini-3.8-flash")
    assert type(gemini_metric).__name__ == "AnswerRelevancy"
    assert gemini_metric.strictness == 1

    from ragas.metrics import answer_relevancy

    assert select_relevancy_metric("qwen2.5:7b") is answer_relevancy


def test_load_golden_map_missing_and_invalid(tmp_path, monkeypatch):
    evaluator = RagasEvaluator(settings=_hermetic_settings(monkeypatch, tmp_path))
    assert evaluator.load_golden_map(tmp_path / "nao_existe.json") == {}

    bad = tmp_path / "bad.json"
    bad.write_text("{invalido", encoding="utf-8")
    assert evaluator.load_golden_map(bad) == {}


def test_load_golden_map_normalizes_keys(tmp_path, monkeypatch):
    evaluator = RagasEvaluator(settings=_hermetic_settings(monkeypatch, tmp_path))
    path = _golden_file(tmp_path, [{"question": "  Qual o PRAZO? ", "ground_truth": "30 min"}])
    golden_map = evaluator.load_golden_map(path)
    assert golden_map["qual o prazo?"]["ground_truth"] == "30 min"


def test_prepare_dataset_joins_golden_and_context(tmp_path, monkeypatch):
    settings = _hermetic_settings(monkeypatch, tmp_path)
    settings.pops_dir = tmp_path
    (tmp_path / "pop_a.txt").write_text("CONTEXTO DO POP", encoding="utf-8")
    golden = _golden_file(
        tmp_path,
        [
            {
                "question": "Qual o prazo?",
                "ground_truth": "30 min",
                "question_type": "REGULATORY_TIMELINE",
                "source_document": "pop_a.txt",
            }
        ],
    )
    evaluator = RagasEvaluator(settings=settings)
    records = [
        _rec("Qual o prazo?"),
        _rec("Falha", response=None, status=RagExecutionStatus.ERROR),
        _rec("Sem golden"),
    ]

    ds = evaluator.prepare_dataset(records, golden)

    assert len(ds) == 2  # erro sem resposta é filtrado
    assert ds[0]["ground_truth"] == "30 min"
    assert ds[0]["contexts"] == ["CONTEXTO DO POP"]
    assert ds[0]["question_type"] == "REGULATORY_TIMELINE"
    assert ds[1]["ground_truth"] == "N/A"  # sem entrada no golden
    assert ds[1]["contexts"] == [
        "Regras operacionais padrão de compliance bancário extraídas do grafo."
    ]


def test_prepare_dataset_empty_raises(tmp_path, monkeypatch):
    evaluator = RagasEvaluator(settings=_hermetic_settings(monkeypatch, tmp_path))
    golden = _golden_file(tmp_path, [])
    with pytest.raises(EvaluationError):
        evaluator.prepare_dataset([_rec("Q?", response=None)], golden)


class _FakeResult:
    def __init__(self, df: pd.DataFrame):
        self._df = df

    def to_pandas(self) -> pd.DataFrame:
        return self._df


def test_run_evaluation_uses_injected_fn(tmp_path, monkeypatch):
    settings = _hermetic_settings(monkeypatch, tmp_path)
    golden = _golden_file(
        tmp_path, [{"question": "Q?", "ground_truth": "G", "question_type": "EDGE_CASE"}]
    )
    captured: dict = {}

    def fake_evaluate(dataset, metrics, llm, embeddings, **kwargs):
        captured["n"] = len(dataset)
        captured["metrics"] = len(metrics)
        captured["llm"] = llm
        captured["embeddings"] = embeddings
        captured["run_config"] = kwargs["run_config"]
        return _FakeResult(pd.DataFrame({"faithfulness": [0.9]}))

    evaluator = RagasEvaluator(
        settings=settings,
        judge_llm_factory=lambda: "fake-llm",
        embeddings_factory=lambda: "fake-emb",
        evaluate_fn=fake_evaluate,
    )
    df = evaluator.run_evaluation([_rec("Q?")], golden_path=golden)

    assert df["faithfulness"].tolist() == [0.9]
    assert captured["n"] == 1
    assert captured["metrics"] == 4
    assert captured["llm"] == "fake-llm"
    assert captured["embeddings"] == "fake-emb"
    assert captured["run_config"].max_workers == settings.ragas.max_workers


def test_run_evaluation_wraps_error(tmp_path, monkeypatch):
    settings = _hermetic_settings(monkeypatch, tmp_path)
    golden = _golden_file(tmp_path, [{"question": "Q?", "ground_truth": "G"}])

    def boom(*args, **kwargs):
        raise RuntimeError("ragas down")

    evaluator = RagasEvaluator(
        settings=settings,
        judge_llm_factory=lambda: "fake-llm",
        embeddings_factory=lambda: "fake-emb",
        evaluate_fn=boom,
    )
    with pytest.raises(EvaluationError):
        evaluator.run_evaluation([_rec("Q?")], golden_path=golden)
