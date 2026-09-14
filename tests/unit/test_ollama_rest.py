"""Regressão Fase 0: OllamaChatClient via REST nativa (/api/tags, /api/chat, /api/embed).

Congela o comportamento introduzido em c18a0f6 (num_ctx injetado, NDJSON stream).
Sem rede: httpx.AsyncClient é substituído por fakes via monkeypatch.
"""

import httpx
import numpy as np
import pytest

from ragbench.config import ChatSettings
from ragbench.infrastructure.ollama_client import OllamaChatClient


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("erro", request=None, response=None)  # type: ignore[arg-type]

    def json(self) -> dict:
        return self._payload


class FakeStreamResponse:
    def __init__(self, lines: list[str], status_code: int = 200):
        self._lines = lines
        self.status_code = status_code

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("erro", request=None, response=None)  # type: ignore[arg-type]

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class FakeAsyncClient:
    """Fake de httpx.AsyncClient: comportamento dirigido por atributos de classe."""

    # Configurado por teste
    get_response: FakeResponse = FakeResponse(200)
    post_response: FakeResponse = FakeResponse(200, {"message": {"content": "oi"}})
    stream_lines: list[str] = []
    get_error: Exception | None = None
    last_post_json: dict | None = None
    last_post_url: str | None = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, **kwargs):
        if type(self).get_error is not None:
            raise type(self).get_error
        return type(self).get_response

    async def post(self, url, **kwargs):
        type(self).last_post_url = url
        type(self).last_post_json = kwargs.get("json")
        return type(self).post_response

    def stream(self, method, url, **kwargs):
        type(self).last_post_url = url
        type(self).last_post_json = kwargs.get("json")
        return FakeStreamResponse(type(self).stream_lines)


@pytest.fixture
def _fake_http():
    FakeAsyncClient.get_response = FakeResponse(200)
    FakeAsyncClient.post_response = FakeResponse(200, {"message": {"content": "oi"}})
    FakeAsyncClient.stream_lines = []
    FakeAsyncClient.get_error = None
    FakeAsyncClient.last_post_json = None
    FakeAsyncClient.last_post_url = None
    return FakeAsyncClient


def _settings() -> ChatSettings:
    # Hermético: não depende dos defaults do código (que mudam com a migração Gemini).
    return ChatSettings(
        base_url="http://localhost:11434/v1/",
        llm_model="fake-model",
        num_ctx=4096,
    )


@pytest.mark.asyncio
async def test_check_health_ok(_fake_http):
    client = OllamaChatClient(_settings(), http_client_factory=_fake_http)
    assert await client.check_health() is True


@pytest.mark.asyncio
async def test_check_health_non_200_is_false(_fake_http):
    _fake_http.get_response = FakeResponse(500)
    client = OllamaChatClient(_settings(), http_client_factory=_fake_http)
    assert await client.check_health() is False


@pytest.mark.asyncio
async def test_check_health_exception_is_false(_fake_http):
    _fake_http.get_error = ConnectionError("down")
    client = OllamaChatClient(_settings(), http_client_factory=_fake_http)
    assert await client.check_health() is False


@pytest.mark.asyncio
async def test_chat_non_stream_returns_content_and_injects_num_ctx(_fake_http):
    _fake_http.post_response = FakeResponse(200, {"message": {"content": "resposta-x"}})
    client = OllamaChatClient(_settings(), http_client_factory=_fake_http)
    out = await client.generate_completion(messages=[{"role": "user", "content": "oi"}])

    assert out == "resposta-x"
    payload = _fake_http.last_post_json
    assert payload is not None
    assert payload["options"]["num_ctx"] == 4096
    assert payload["model"] == "fake-model"  # fallback do settings
    assert _fake_http.last_post_url is not None and _fake_http.last_post_url.endswith("/api/chat")


@pytest.mark.asyncio
async def test_chat_stream_concatenates_and_ignores_invalid_line(_fake_http):
    import json

    _fake_http.stream_lines = [
        json.dumps({"message": {"content": "Olá, "}}),
        "linha-invalida{{{",
        json.dumps({"message": {"content": "mundo!"}}),
        json.dumps({"message": {"content": ""}}),
    ]
    client = OllamaChatClient(_settings(), http_client_factory=_fake_http)
    gen = await client.generate_completion(
        messages=[{"role": "user", "content": "oi"}], stream=True
    )
    assert gen is not None
    chunks = [c async for c in gen]  # type: ignore[union-attr]
    assert chunks == ["Olá, ", "mundo!"]


@pytest.mark.asyncio
async def test_get_embeddings_returns_array(_fake_http):
    _fake_http.post_response = FakeResponse(200, {"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]})
    client = OllamaChatClient(_settings(), http_client_factory=_fake_http)
    arr = await client.get_embeddings(texts=["a", "b"], embedding_dim=3)

    assert isinstance(arr, np.ndarray)
    assert arr.shape == (2, 3)


@pytest.mark.asyncio
async def test_get_embeddings_empty_returns_zeros(_fake_http):
    _fake_http.post_response = FakeResponse(200, {"embeddings": []})
    client = OllamaChatClient(_settings(), http_client_factory=_fake_http)
    arr = await client.get_embeddings(texts=["a", "b"], embedding_dim=4)

    assert arr.shape == (2, 4)
    assert float(arr.sum()) == 0.0


def test_api_urls_strip_v1_suffix():
    client = OllamaChatClient(_settings(), http_client_factory=FakeAsyncClient)
    assert client.chat_url == "http://localhost:11434/api/chat"
    assert client.tags_url == "http://localhost:11434/api/tags"
    assert client.embed_url == "http://localhost:11434/api/embed"


def test_build_chat_payload_injects_num_ctx_and_model_fallback():
    client = OllamaChatClient(_settings(), http_client_factory=FakeAsyncClient)
    payload = client.build_chat_payload(
        model=None, messages=[{"role": "user", "content": "oi"}], temperature=None, stream=False
    )
    assert payload["model"] == "fake-model"
    assert payload["options"] == {"temperature": 0.0, "num_ctx": 4096}
    assert payload["stream"] is False


def test_build_chat_payload_explicit_overrides():
    client = OllamaChatClient(_settings(), http_client_factory=FakeAsyncClient)
    payload = client.build_chat_payload(
        model="outro-modelo", messages=None, temperature=0.7, stream=True
    )
    assert payload["model"] == "outro-modelo"
    assert payload["messages"] == []
    assert payload["options"]["temperature"] == 0.7
