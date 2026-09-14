"""Fase 1+2: backoff puro e retry-loop do ResilientOllamaClient (sem rede)."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError

from ragbench.config import OllamaSettings
from ragbench.core.exceptions import OllamaConnectionError
from ragbench.infrastructure.ollama_client import ResilientOllamaClient


def _client(**overrides) -> ResilientOllamaClient:
    settings = OllamaSettings(**overrides)
    return ResilientOllamaClient(
        settings,
        client=object(),
        genai_client=object(),  # type: ignore[arg-type]
    )


def test_injected_clients_are_kept():
    sentinel_c, sentinel_g = object(), object()
    client = ResilientOllamaClient(OllamaSettings(), client=sentinel_c, genai_client=sentinel_g)  # type: ignore[arg-type]
    assert client.client is sentinel_c
    assert client.genai_client is sentinel_g


def test_rate_limit_delay_within_bounds():
    client = _client(retry_initial_delay=5.0, retry_backoff_factor=2.0, retry_max_delay=60.0)
    for attempt in range(1, 7):
        ceiling = min(60.0, 5.0 * (2.0 ** (attempt - 1)))
        for _ in range(50):
            delay = client.calc_rate_limit_delay(attempt)
            assert 0.0 <= delay <= ceiling


def test_rate_limit_delay_respects_small_ceiling():
    # jitter_min (2.0) acima do teto calculado -> floor colapsa para o teto, sem erro.
    client = _client(retry_initial_delay=0.5, retry_backoff_factor=1.0, retry_max_delay=60.0)
    for _ in range(50):
        assert 0.0 <= client.calc_rate_limit_delay(1) <= 0.5


def _rate_limit_error() -> RateLimitError:
    resp = httpx.Response(429, request=httpx.Request("POST", "http://gemini"))
    return RateLimitError("rate limit", response=resp, body={})


class _FakeCompletions:
    def __init__(self, script: list):
        self.script = list(script)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        behavior = self.script.pop(0)
        if isinstance(behavior, Exception):
            raise behavior
        return behavior


class _FakeOpenAIClient:
    def __init__(self, script: list):
        self.chat = SimpleNamespace(completions=_FakeCompletions(script))


def _ok_response(content: str | None = "hello") -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _stream_chunk(content: str | None) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content))])


@pytest.fixture
def _no_sleep(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return sleeps


def _resilient(script: list, **overrides) -> tuple[ResilientOllamaClient, _FakeOpenAIClient]:
    settings = OllamaSettings(
        rate_limit_interval_seconds=0.0, completion_max_attempts=2, **overrides
    )
    fake = _FakeOpenAIClient(script)
    client = ResilientOllamaClient(settings, client=fake, genai_client=object())  # type: ignore[arg-type]
    return client, fake


@pytest.mark.asyncio
async def test_completion_success_first_try(_no_sleep):
    client, fake = _resilient([_ok_response("hello")])
    out = await client.generate_completion(model="m", messages=[{"role": "user", "content": "oi"}])
    assert out == "hello"
    assert len(fake.chat.completions.calls) == 1
    assert fake.chat.completions.calls[0]["model"] == "m"
    assert _no_sleep == []


@pytest.mark.asyncio
async def test_completion_rate_limit_then_success(_no_sleep):
    client, fake = _resilient([_rate_limit_error(), _ok_response("ok")])
    out = await client.generate_completion(model="m", messages=[{"role": "user", "content": "oi"}])
    assert out == "ok"
    assert len(fake.chat.completions.calls) == 2
    assert len(_no_sleep) == 1


@pytest.mark.asyncio
async def test_completion_rate_limit_exhausted(_no_sleep):
    client, _ = _resilient([_rate_limit_error(), _rate_limit_error()])
    with pytest.raises(OllamaConnectionError, match="Rate limit"):
        await client.generate_completion(model="m", messages=[])
    assert len(_no_sleep) == 1  # dorme entre tentativas, mas não após a última


@pytest.mark.asyncio
async def test_completion_generic_error_wraps(_no_sleep):
    client, _ = _resilient([RuntimeError("x"), RuntimeError("y")])
    with pytest.raises(OllamaConnectionError, match="Falha no modelo"):
        await client.generate_completion(model="m", messages=[])


@pytest.mark.asyncio
async def test_completion_stream_yields_chunks(_no_sleep):
    async def chunks():
        for c in [_stream_chunk("a"), _stream_chunk(None), _stream_chunk("b")]:
            yield c

    client, _ = _resilient([chunks()])
    gen = await client.generate_completion(model="m", messages=[], stream=True)
    assert gen is not None
    assert [c async for c in gen] == ["a", "b"]  # type: ignore[union-attr]
