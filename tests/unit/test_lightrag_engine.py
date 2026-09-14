"""Fase 2: LightRAGEngine sem LightRAG real (rag_factory + fakes injetados)."""

import os

import numpy as np
import pytest
from lightrag.prompt import PROMPTS

from ragbench.config import BenchmarkSettings
from ragbench.core.models import SearchMode
from ragbench.engines.lightrag_engine import (
    LightRAGEngine,
    build_entity_extraction_prompt,
    build_llm_messages,
)


@pytest.fixture
def _settings(monkeypatch, tmp_path) -> BenchmarkSettings:
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__")):
            monkeypatch.delenv(key, raising=False)
    settings = BenchmarkSettings(_env_file=None)
    settings.storage_dir = tmp_path / "graph"
    settings.lightrag.llm_model = "idx-model"
    settings.chat.llm_model = "chat-model"
    return settings


@pytest.fixture
def _restore_prompts():
    snapshot = dict(PROMPTS)
    yield
    PROMPTS.clear()
    PROMPTS.update(snapshot)


class _FakeLLMClient:
    def __init__(self):
        self.calls: list[dict] = []

    async def generate_completion(self, **kwargs):
        self.calls.append(kwargs)
        return "resposta-fake"

    async def get_embeddings(self, **kwargs):
        return np.zeros((1, 3))


class _FakeRag:
    instances: list["_FakeRag"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.initialized = False
        self.finalized = False
        self.inserted: list[str] = []
        self.queries: list[tuple] = []
        type(self).instances.append(self)

    async def initialize_storages(self):
        self.initialized = True

    async def finalize_storages(self):
        self.finalized = True

    async def aquery(self, query, param=None):
        self.queries.append((query, param))
        return f"eco:{query}"

    async def ainsert(self, text):
        self.inserted.append(text)


@pytest.fixture
def _fake_rag_cls():
    _FakeRag.instances.clear()
    return _FakeRag


def test_build_entity_prompt_appends_once():
    out = build_entity_extraction_prompt("BASE")
    assert out.startswith("BASE")
    assert "BANKING COMPLIANCE" in out
    # Idempotente
    assert build_entity_extraction_prompt(out) == out


def test_build_llm_messages_order_and_constraint():
    msgs = build_llm_messages(
        "pergunta?", system_prompt="SYS", history_messages=[{"role": "user", "content": "h"}]
    )
    assert msgs[0]["role"] == "system"
    assert "SYS" in msgs[0]["content"]
    assert "pt-BR" in msgs[0]["content"]
    assert msgs[1] == {"role": "user", "content": "h"}
    assert msgs[-1] == {"role": "user", "content": "pergunta?"}


def test_invalid_role_raises_without_network(_settings):
    with pytest.raises(ValueError, match="role inválido"):
        LightRAGEngine(settings=_settings, role="treinamento")


def test_role_aware_model_and_inject_prompts(_settings, _restore_prompts):
    fake = _FakeLLMClient()
    index = LightRAGEngine(
        settings=_settings,
        ollama_client=fake,
        chat_client=fake,
        role="index",  # type: ignore[arg-type]
    )
    chat = LightRAGEngine(
        settings=_settings,
        ollama_client=fake,
        chat_client=fake,
        role="chat",  # type: ignore[arg-type]
    )
    assert index.llm_model == "idx-model"
    assert chat.llm_model == "chat-model"
    assert "BANKING COMPLIANCE" in PROMPTS.get("entity_extraction", "")


@pytest.mark.asyncio
async def test_custom_llm_func_delegates_role_model(_settings, _restore_prompts):
    fake = _FakeLLMClient()
    engine = LightRAGEngine(
        settings=_settings,
        ollama_client=fake,
        chat_client=fake,
        role="chat",  # type: ignore[arg-type]
    )
    out = await engine._custom_llm_func("oi?", system_prompt="SYS")
    assert out == "resposta-fake"
    assert fake.calls[0]["model"] == "chat-model"
    assert fake.calls[0]["temperature"] == _settings.chat.temperature


@pytest.mark.asyncio
async def test_initialize_uses_factory_and_role_timeouts(
    _settings, _restore_prompts, _fake_rag_cls
):
    fake = _FakeLLMClient()
    engine = LightRAGEngine(
        settings=_settings,
        ollama_client=fake,  # type: ignore[arg-type]
        chat_client=fake,  # type: ignore[arg-type]
        role="chat",
        rag_factory=_fake_rag_cls,
    )
    await engine.initialize()

    assert len(_fake_rag_cls.instances) == 1
    rag = _fake_rag_cls.instances[0]
    assert rag.initialized is True
    assert rag.kwargs["llm_model_max_async"] == _settings.lightrag.chat_llm_model_max_async
    assert rag.kwargs["chunk_token_size"] == _settings.lightrag.chunk_token_size
    assert engine.rag is rag


@pytest.mark.asyncio
async def test_aquery_requires_initialize(_settings, _restore_prompts):
    fake = _FakeLLMClient()
    engine = LightRAGEngine(
        settings=_settings,
        ollama_client=fake,
        chat_client=fake,  # type: ignore[arg-type]
    )
    with pytest.raises(RuntimeError, match="não foi inicializado"):
        await engine.aquery("q")


@pytest.mark.asyncio
async def test_aquery_maps_mode_and_top_k(_settings, _restore_prompts, _fake_rag_cls):
    fake = _FakeLLMClient()
    engine = LightRAGEngine(
        settings=_settings,
        ollama_client=fake,  # type: ignore[arg-type]
        chat_client=fake,  # type: ignore[arg-type]
        rag_factory=_fake_rag_cls,
    )
    await engine.initialize()
    out = await engine.aquery("qq?", mode=SearchMode.LOCAL, top_k=3)

    assert out == "eco:qq?"
    _, param = _fake_rag_cls.instances[0].queries[0]
    assert param.mode == "local"
    assert param.top_k == 3


@pytest.mark.asyncio
async def test_ainsert_and_finalize(_settings, _restore_prompts, _fake_rag_cls):
    fake = _FakeLLMClient()
    engine = LightRAGEngine(
        settings=_settings,
        ollama_client=fake,  # type: ignore[arg-type]
        chat_client=fake,  # type: ignore[arg-type]
        rag_factory=_fake_rag_cls,
    )
    with pytest.raises(RuntimeError, match="não foi inicializado"):
        await engine.ainsert("doc")

    await engine.initialize()
    await engine.ainsert("doc1")
    await engine.finalize()
    rag = _fake_rag_cls.instances[0]
    assert rag.inserted == ["doc1"]
    assert rag.finalized is True
