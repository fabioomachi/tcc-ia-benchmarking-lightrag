"""Fase 2: generate_ragas_markdown_report sem LLM (DataFrames sintéticos)."""

import pandas as pd

from ragbench.reporting.reporters import BenchmarkReporter


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_ragas_report_means_and_groups(tmp_path):
    df = _df(
        [
            {
                "faithfulness": 0.9,
                "answer_relevancy": 0.8,
                "context_recall": 0.7,
                "context_precision": 0.6,
                "question_type": "EDGE_CASE",
                "question": "Q1",
                "answer": "A1",
                "ground_truth": "G1",
            },
            {
                "faithfulness": 0.5,
                "answer_relevancy": 0.4,
                "context_recall": 0.3,
                "context_precision": 0.2,
                "question_type": "EDGE_CASE",
                "question": "Q2",
                "answer": "A2",
                "ground_truth": "G2",
            },
        ]
    )
    out = tmp_path / "ragas.md"
    result = BenchmarkReporter.generate_ragas_markdown_report(df, out)

    assert result == out
    text = out.read_text(encoding="utf-8")
    assert "Faithfulness**: `0.7000`" in text
    assert "EDGE_CASE" in text
    assert "Pior score em `faithfulness`" in text
    assert "Q2" in text  # pior caso referenciado


def test_ragas_report_without_question_type(tmp_path):
    df = _df([{"faithfulness": 1.0, "question": "Q", "answer": "A"}])
    out = tmp_path / "ragas.md"
    BenchmarkReporter.generate_ragas_markdown_report(df, out)
    text = out.read_text(encoding="utf-8")
    assert "Faithfulness**: `1.0000`" in text
    assert "Categoria" not in text


def test_ragas_report_all_nan_metric_skips_worst(tmp_path):
    df = _df(
        [
            {
                "faithfulness": float("nan"),
                "question_type": "EDGE_CASE",
                "question": "Q",
                "answer": "A",
                "ground_truth": "G",
            }
        ]
    )
    out = tmp_path / "ragas.md"
    BenchmarkReporter.generate_ragas_markdown_report(df, out)
    assert out.exists()


def test_ragas_report_empty_df(tmp_path):
    out = tmp_path / "nested" / "ragas.md"
    result = BenchmarkReporter.generate_ragas_markdown_report(pd.DataFrame(), out)
    assert result == out
    assert "Nenhum dado" in out.read_text(encoding="utf-8")
