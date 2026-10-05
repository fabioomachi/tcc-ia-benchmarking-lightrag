"""Contratos Ports & Adapters: engines conformam BaseRAGPipeline em runtime."""

import numpy as np
import pytest
from pydantic import ValidationError

from ragbench.conversational.router import DOC_ACESSO, RouteInfo, route_by_graph
from ragbench.core.interfaces import BaseCache, BaseExecutionStorage, BaseRAGPipeline
from ragbench.core.models import QueryExecutionRecord
from ragbench.engines.decision_tree_engine import DecisionTreeEngine
from ragbench.engines.direct_llm_engine import DirectLLMEngine
from ragbench.engines.lightrag_engine import LightRAGEngine
from ragbench.infrastructure.semantic_cache import SemanticCache
from ragbench.infrastructure.storage import JsonlExecutionStorage, SQLiteExecutionStorage


def test_protocols_sao_runtime_checkable():
    assert isinstance(LightRAGEngine, type)
    assert hasattr(BaseRAGPipeline, "__protocol_attrs__") or hasattr(
        BaseRAGPipeline, "_is_runtime_protocol"
    )
    assert BaseRAGPipeline._is_runtime_protocol is True
    assert BaseCache._is_runtime_protocol is True
    assert BaseExecutionStorage._is_runtime_protocol is True


def test_engines_conformam_base_rag_pipeline():
    required = (
        "llm_model",
        "get_query_embeddings",
        "initialize",
        "aquery",
        "ainsert",
        "finalize",
    )
    for cls in (LightRAGEngine, DirectLLMEngine, DecisionTreeEngine):
        # Herança explícita (não só estrutural) + membros do contrato presentes.
        # (issubclass vs Protocol com data member levanta TypeError; MRO basta.)
        assert BaseRAGPipeline in cls.__mro__, f"{cls.__name__} não herda BaseRAGPipeline"
        for member in required:
            assert hasattr(cls, member), f"{cls.__name__} sem {member}"


def test_storages_e_cache_conformam_protocolos(tmp_path):
    assert isinstance(SemanticCache(), BaseCache)
    assert isinstance(SQLiteExecutionStorage(tmp_path / "c.sqlite3"), BaseExecutionStorage)
    assert isinstance(JsonlExecutionStorage(tmp_path / "c.jsonl"), BaseExecutionStorage)


def test_route_info_acesso_dict_like():
    index = {DOC_ACESSO: ["senha de 6 digitos bloqueio codigo"], "outro.md": ["fatura email"]}
    route = route_by_graph("bloqueio da senha de 6 digitos", index, filled={})
    assert isinstance(route, RouteInfo)
    assert route["doc"] == DOC_ACESSO
    assert route.get("confident") is True
    assert route.mode == "local"
    assert route.top_k == 10


def test_record_validators_top_k_zero_ok_tree_direct():
    rec = QueryExecutionRecord(query="q", top_k=0)
    assert rec.top_k == 0
    with pytest.raises(ValidationError):
        QueryExecutionRecord(query="q", top_k=-1)
    with pytest.raises(ValidationError):
        QueryExecutionRecord(query="q", similarity_score=1.5)
    with pytest.raises(ValidationError):
        QueryExecutionRecord(query="q", total_latency_seconds=-0.1)


def test_semantic_cache_vetorizado_hit_miss():
    cache = SemanticCache(threshold=0.9)
    v = np.array([1.0, 0.0, 0.0])
    cache.add(v, "resp")
    resp, sim = cache.get(np.array([1.0, 0.0, 0.0]))
    assert resp == "resp"
    assert sim >= 0.9
    resp2, _ = cache.get(np.array([0.0, 1.0, 0.0]))
    assert resp2 is None
