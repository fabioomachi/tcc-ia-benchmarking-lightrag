"""Regressão Fase 0: guards defensivos de generate_execution_markdown_report.

Congela o comportamento introduzido em c18a0f6 (DF vazio, Enum, colunas ausentes).
"""

from ragbench.core.models import (
    QueryExecutionRecord,
    QueryInteractionSource,
    RagExecutionStatus,
    SearchMode,
)
from ragbench.reporting.reporters import BenchmarkReporter


class _Stub:
    """Stub duck-typed: model_dump() retorna dict parcial (simula coluna ausente)."""

    def __init__(self, payload: dict):
        self._payload = payload

    def model_dump(self) -> dict:
        return dict(self._payload)


def _rec(idx: int, **overrides) -> QueryExecutionRecord:
    base = {
        "index": idx,
        "query": f"Pergunta {idx}",
        "response": f"Resposta {idx}",
        "mode": SearchMode.HYBRID,
        "source": QueryInteractionSource.LIGHTRAG_ENGINE,
        "status": RagExecutionStatus.SUCCESS,
        "total_latency_seconds": 1.0,
    }
    base.update(overrides)
    return QueryExecutionRecord(**base)


def test_empty_records_writes_fallback_and_creates_parents(tmp_path):
    out = tmp_path / "nested" / "dir" / "resumo.md"
    result = BenchmarkReporter.generate_execution_markdown_report([], out)
    assert result == out
    assert out.exists()
    assert "Nenhum registro" in out.read_text(encoding="utf-8")


def test_enum_status_and_source_counted(tmp_path):
    out = tmp_path / "resumo.md"
    records = [
        _rec(0, status=RagExecutionStatus.SUCCESS),
        _rec(1, status=RagExecutionStatus.ERROR, source=QueryInteractionSource.SEMANTIC_CACHE),
        _rec(2, status=RagExecutionStatus.SUCCESS),
    ]
    BenchmarkReporter.generate_execution_markdown_report(records, out)
    text = out.read_text(encoding="utf-8")
    assert "Total de Consultas Submetidas:** 3" in text
    assert "Concluídas com Sucesso:** 2" in text
    assert "Semantic Cache (Hit):** 1" in text


def test_missing_status_column_defaults_to_total(tmp_path):
    out = tmp_path / "resumo.md"
    stubs = [
        _Stub({"index": 0, "query": "q", "response": "r", "mode": "hybrid"}),
        _Stub({"index": 1, "query": "q2", "response": "r2", "mode": "hybrid"}),
    ]
    BenchmarkReporter.generate_execution_markdown_report(stubs, out)  # type: ignore[arg-type]
    text = out.read_text(encoding="utf-8")
    assert "Total de Consultas Submetidas:** 2" in text
    assert "Concluídas com Sucesso:** 2" in text


def test_missing_ttft_column_does_not_raise(tmp_path):
    out = tmp_path / "resumo.md"
    stubs = [_Stub({"index": 0, "query": "q", "response": "r", "status": "success"})]
    BenchmarkReporter.generate_execution_markdown_report(stubs, out)  # type: ignore[arg-type]
    assert out.exists()
