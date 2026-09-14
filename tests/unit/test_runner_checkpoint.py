"""Regressão Fase 0: checkpoint por query + consumo de stream no runner.

Congela o comportamento introduzido em c18a0f6:
- worker persiste cada record (save_record) inclusive no caminho de erro;
- aquery retornando AsyncGenerator é consumido;
- resposta vazia marca ERROR sem popular o cache.
"""

from collections.abc import AsyncGenerator

import numpy as np
import pytest

from ragbench.config import BenchmarkSettings
from ragbench.core.models import RagExecutionStatus
from ragbench.infrastructure.semantic_cache import SemanticCache
from ragbench.infrastructure.storage import SQLiteExecutionStorage
from ragbench.runner import BenchmarkRunner


class FakeEngine:
    """Fake de LightRAGEngine com comportamento programável por pergunta."""

    def __init__(self, behaviors: dict[str, object]):
        self.behaviors = behaviors
        self.llm_model = "fake-model"
        self.calls: list[str] = []

    async def get_query_embeddings(self, texts: list[str]) -> np.ndarray:
        return np.array([[1.0, 0.0, 0.0] for _ in texts])

    async def aquery(
        self, query: str, mode=None, top_k: int = 5, stream: bool = False
    ) -> str | AsyncGenerator[str, None]:
        self.calls.append(query)
        behavior = self.behaviors.get(query, "default-resposta")

        if isinstance(behavior, Exception):
            raise behavior
        if isinstance(behavior, list):
            chunks = behavior

            async def _gen() -> AsyncGenerator[str, None]:
                for c in chunks:
                    yield c

            return _gen()
        return str(behavior)


def _make_runner(tmp_path, behaviors: dict[str, object]) -> tuple[BenchmarkRunner, FakeEngine]:
    storage = SQLiteExecutionStorage(tmp_path / "ckpt.sqlite3")
    engine = FakeEngine(behaviors)
    settings = BenchmarkSettings(_env_file=None)
    runner = BenchmarkRunner(
        engine=engine,  # type: ignore[arg-type]
        storage=storage,
        cache=SemanticCache(threshold=0.99),
        settings=settings,
    )
    return runner, engine


@pytest.mark.asyncio
async def test_str_response_success_and_checkpoint_saved(tmp_path):
    runner, _ = _make_runner(tmp_path, {"q1": "resposta-um"})
    records = await runner.execute_batch(
        queries=["q1"], concurrency=2, resume=False, show_progress=False
    )

    assert len(records) == 1
    assert records[0].response == "resposta-um"
    assert records[0].status == RagExecutionStatus.SUCCESS
    # Checkpoint persistido: recarrega do sqlite
    assert runner.storage.get_completed_indices() == {0}


@pytest.mark.asyncio
async def test_stream_response_is_consumed(tmp_path):
    runner, _ = _make_runner(tmp_path, {"qs": ["Olá, ", "mundo!"]})
    records = await runner.execute_batch(
        queries=["qs"], concurrency=2, resume=False, show_progress=False
    )

    assert len(records) == 1
    assert records[0].response == "Olá, mundo!"
    assert records[0].status == RagExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_empty_response_marks_error_and_still_checkpoints(tmp_path):
    runner, _ = _make_runner(tmp_path, {"qv": "   "})
    records = await runner.execute_batch(
        queries=["qv"], concurrency=2, resume=False, show_progress=False
    )

    assert len(records) == 1
    assert records[0].status == RagExecutionStatus.ERROR
    assert "vazia" in (records[0].error_message or "")
    # Mesmo com erro, o record foi persistido (checkpoint por query)
    assert len(runner.storage.load_all_records()) == 1


@pytest.mark.asyncio
async def test_engine_exception_marks_error_and_checkpoints(tmp_path):
    runner, _ = _make_runner(tmp_path, {"qe": RuntimeError("boom")})
    records = await runner.execute_batch(
        queries=["qe"], concurrency=2, resume=False, show_progress=False
    )

    assert len(records) == 1
    assert records[0].status == RagExecutionStatus.ERROR
    assert "RuntimeError" in (records[0].error_message or "")
    assert len(runner.storage.load_all_records()) == 1


@pytest.mark.asyncio
async def test_resume_skips_completed_queries(tmp_path):
    storage = SQLiteExecutionStorage(tmp_path / "ckpt.sqlite3")
    settings = BenchmarkSettings(_env_file=None)
    # Pré-popula índice 0 como concluído
    runner_seed, _ = _make_runner(tmp_path, {})
    runner_seed.storage = storage
    from ragbench.core.models import QueryExecutionRecord

    storage.save_record(QueryExecutionRecord(index=0, query="q0", response="old"))

    engine = FakeEngine({"q0": "nova-resposta", "q1": "resp-1"})
    runner = BenchmarkRunner(
        engine=engine,  # type: ignore[arg-type]
        storage=storage,
        cache=SemanticCache(threshold=0.99),
        settings=settings,
    )
    await runner.execute_batch(
        queries=["q0", "q1"], concurrency=2, resume=True, show_progress=False
    )

    assert engine.calls == ["q1"]
    all_recs = storage.load_all_records()
    assert {r.index for r in all_recs} == {0, 1}
    # q0 mantém a resposta original (não sobrescrita)
    assert next(r for r in all_recs if r.index == 0).response == "old"
