"""Parada graciosa por cota (429) no `index` + limpeza do resíduo parcial."""

import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from ragbench.cli import app
from ragbench.cli_commands import deps
from ragbench.cli_commands.index_cmd import QUOTA_EXIT_CODE
from ragbench.config import BenchmarkSettings
from ragbench.core.exceptions import OllamaConnectionError, QuotaExhaustedError
from ragbench.engines.lightrag_engine import LightRAGEngine
from ragbench.infrastructure.index_manifest import manifest_path
from ragbench.infrastructure.ollama_client import (
    ResilientOllamaClient,
    is_quota_message,
)


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


def _make_pops(settings: BenchmarkSettings, names: list[str]) -> None:
    settings.pops_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        (settings.pops_dir / name).write_text(f"conteudo de {name}\n", encoding="utf-8")


class _QuotaEngine:
    """Falha com QuotaExhaustedError no b.txt; registra limpeza."""

    inserted: list[str] = []
    cleaned: list[str] = []
    finalized = 0

    def __init__(self):
        self.llm_model = "fake-model"

    @classmethod
    def for_index(cls, settings=None):
        return cls()

    async def initialize(self):
        pass

    async def finalize(self):
        type(self).finalized += 1

    async def ainsert(self, text: str):
        type(self).inserted.append(text)
        if "DOCUMENTO_ORIGEM: b.txt" in text:
            raise QuotaExhaustedError("Cota da API esgotada no modelo fake.")

    async def adelete_doc_by_filename(self, filename: str) -> bool:
        type(self).cleaned.append(filename)
        return True

    async def get_doc_status_by_filename(self, filename: str) -> str | None:
        return "processed"


class _SilentFailEngine(_QuotaEngine):
    """ainsert não lança, mas o pipeline marca b.txt como failed."""

    inserted: list[str] = []
    cleaned: list[str] = []
    finalized = 0

    async def ainsert(self, text: str):
        type(self).inserted.append(text)

    async def get_doc_status_by_filename(self, filename: str) -> str | None:
        return "failed" if filename == "b.txt" else "processed"


class _FlakyEngine(_QuotaEngine):
    """Falha genérica no b.txt, mas continua o lote."""

    inserted: list[str] = []
    cleaned: list[str] = []
    finalized = 0

    async def ainsert(self, text: str):
        type(self).inserted.append(text)
        if "DOCUMENTO_ORIGEM: b.txt" in text:
            raise ValueError("boom transitório")


class _UncleanableEngine(_QuotaEngine):
    inserted: list[str] = []
    cleaned: list[str] = []
    finalized = 0

    async def ainsert(self, text: str):
        type(self).inserted.append(text)
        if "DOCUMENTO_ORIGEM: b.txt" in text:
            raise ValueError("boom transitório")

    async def adelete_doc_by_filename(self, filename: str) -> bool:
        type(self).cleaned.append(filename)
        return False


def _reset(*engines):
    for engine in engines:
        engine.inserted.clear()
        engine.cleaned.clear()
        engine.finalized = 0


def _ordered_discovery(monkeypatch, names: list[str]):
    import ragbench.cli_commands.index_cmd as index_mod

    monkeypatch.setattr(
        index_mod,
        "discover_pop_files",
        lambda target_dir: [target_dir / name for name in names],
    )


def test_quota_stops_batch_cleans_current_and_exits_3(monkeypatch, tmp_path):
    import ragbench.cli_commands.index_cmd as index_mod

    settings = _settings(monkeypatch, tmp_path)
    _reset(_QuotaEngine)
    monkeypatch.setattr(index_mod, "LightRAGEngine", _QuotaEngine)
    _make_pops(settings, ["a.txt", "b.txt", "c.txt"])
    _ordered_discovery(monkeypatch, ["a.txt", "b.txt", "c.txt"])

    result = CliRunner().invoke(app, ["index"])

    assert result.exit_code == QUOTA_EXIT_CODE, result.output
    assert len(_QuotaEngine.inserted) == 2  # 3º documento nunca tentado
    assert _QuotaEngine.cleaned == ["b.txt"]  # resíduo do corrente removido
    assert _QuotaEngine.finalized == 1  # storages persistidos
    assert "Cota da API esgotada" in result.output
    assert "pendente" in result.output
    # Manifesto só tem o 1º doc: retomada reinsere b.txt do zero.
    from ragbench.infrastructure.index_manifest import load_manifest

    manifest = load_manifest(manifest_path(settings.storage_dir))
    assert [d.filename for d in manifest.documents] == ["a.txt"]


def test_silent_pipeline_failure_cleans_and_skips_manifest(monkeypatch, tmp_path):
    import ragbench.cli_commands.index_cmd as index_mod

    settings = _settings(monkeypatch, tmp_path)
    _reset(_SilentFailEngine)
    monkeypatch.setattr(index_mod, "LightRAGEngine", _SilentFailEngine)
    _make_pops(settings, ["a.txt", "b.txt", "c.txt"])
    _ordered_discovery(monkeypatch, ["a.txt", "b.txt", "c.txt"])

    result = CliRunner().invoke(app, ["index"])

    assert result.exit_code == 0, result.output
    assert len(_SilentFailEngine.inserted) == 3  # sem exceção: lote continua
    assert _SilentFailEngine.cleaned == ["b.txt"]  # parcial limpo mesmo sem raise
    assert "falha silenciosa" in result.output
    from ragbench.infrastructure.index_manifest import load_manifest

    manifest = load_manifest(manifest_path(settings.storage_dir))
    assert sorted(d.filename for d in manifest.documents) == ["a.txt", "c.txt"]


def test_generic_error_cleans_and_continues(monkeypatch, tmp_path):
    import ragbench.cli_commands.index_cmd as index_mod

    settings = _settings(monkeypatch, tmp_path)
    _reset(_FlakyEngine)
    monkeypatch.setattr(index_mod, "LightRAGEngine", _FlakyEngine)
    _make_pops(settings, ["a.txt", "b.txt", "c.txt"])
    _ordered_discovery(monkeypatch, ["a.txt", "b.txt", "c.txt"])

    result = CliRunner().invoke(app, ["index"])

    assert result.exit_code == 0, result.output
    assert len(_FlakyEngine.inserted) == 3  # lote continuou após o erro
    assert _FlakyEngine.cleaned == ["b.txt"]  # parcial do falho foi limpo
    from ragbench.infrastructure.index_manifest import load_manifest

    manifest = load_manifest(manifest_path(settings.storage_dir))
    assert sorted(d.filename for d in manifest.documents) == ["a.txt", "c.txt"]


def test_cleanup_failure_does_not_break_flow(monkeypatch, tmp_path):
    import ragbench.cli_commands.index_cmd as index_mod

    settings = _settings(monkeypatch, tmp_path)
    _reset(_UncleanableEngine)
    monkeypatch.setattr(index_mod, "LightRAGEngine", _UncleanableEngine)
    _make_pops(settings, ["a.txt", "b.txt", "c.txt"])
    _ordered_discovery(monkeypatch, ["a.txt", "b.txt", "c.txt"])

    result = CliRunner().invoke(app, ["index"])

    assert result.exit_code == 0, result.output
    assert len(_UncleanableEngine.inserted) == 3
    assert "Limpeza incompleta" in result.output


def test_is_quota_message():
    assert is_quota_message("429 Quota exceeded for quota metric")
    assert is_quota_message("RESOURCE_EXHAUSTED: billing disabled")
    assert not is_quota_message("connection reset by peer")
    assert not is_quota_message("")


def _rate_limit_error() -> Exception:
    from openai import RateLimitError

    response = httpx.Response(429, request=httpx.Request("POST", "http://fake"))
    return RateLimitError("429 quota exceeded", response=response, body=None)


def test_generate_completion_all_429_raises_quota(monkeypatch):
    async def _no_sleep(_delay):
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    class _Always429:
        async def create(self, **kwargs):
            raise _rate_limit_error()

        @property
        def chat(self):
            from types import SimpleNamespace

            return SimpleNamespace(completions=self)

    settings = BenchmarkSettings(_env_file=None)
    settings.ollama.completion_max_attempts = 2
    client = ResilientOllamaClient(settings.ollama, client=_Always429())

    async def _run():
        with pytest.raises(QuotaExhaustedError):
            await client.generate_completion(model="fake", messages=[])

    asyncio.run(_run())


def test_embeddings_persistent_429_raises_quota(monkeypatch):
    async def _no_sleep(_delay):
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    class _Resp429:
        status_code = 429

    class _FakeCM:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return _Resp429()

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _FakeCM())

    settings = BenchmarkSettings(_env_file=None)
    settings.ollama.embedding_max_attempts = 2
    client = ResilientOllamaClient(settings.ollama, genai_client=object())

    async def _run():
        with pytest.raises(QuotaExhaustedError):
            await client.get_embeddings(model="fake", texts=["oi"])

    asyncio.run(_run())


def test_embeddings_non_429_still_returns_zeros(monkeypatch):
    """Falha não-quota em embeddings levanta (sem envenenar cache com zeros)."""

    async def _no_sleep(_delay):
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    class _FailCM:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _FailCM())

    settings = BenchmarkSettings(_env_file=None)
    settings.ollama.embedding_max_attempts = 2
    client = ResilientOllamaClient(settings.ollama, genai_client=object())

    async def _run():
        with pytest.raises(OllamaConnectionError):
            await client.get_embeddings(model="fake", texts=["oi", "ola"])

    asyncio.run(_run())


class _FakeDeletionResult:
    def __init__(self, status="success"):
        self.status = status


class _FakeRag:
    def __init__(self, fail_ids: set[str] | None = None):
        self.deleted: list[str] = []
        self.fail_ids = fail_ids or set()

    async def adelete_by_doc_id(self, doc_id: str):
        self.deleted.append(doc_id)
        status = "fail" if doc_id in self.fail_ids else "success"
        return _FakeDeletionResult(status)


def _write_doc_status(storage_dir: Path) -> None:
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / "kv_store_doc_status.json").write_text(
        json.dumps(
            {
                "doc-aaa": {
                    "status": "processing",
                    "content_summary": "DOCUMENTO_ORIGEM: b.txt\n\nconteudo parcial",
                },
                "doc-bbb": {
                    "status": "processed",
                    "content_summary": "DOCUMENTO_ORIGEM: a.txt\n\nconteudo ok",
                },
            }
        ),
        encoding="utf-8",
    )


def test_engine_adelete_doc_by_filename_removes_only_non_processed(monkeypatch, tmp_path):
    _settings(monkeypatch, tmp_path)
    settings = deps.get_settings()
    _write_doc_status(settings.storage_dir)
    fake_rag = _FakeRag()

    async def _run():
        engine = LightRAGEngine(
            settings=settings,
            ollama_client=object(),
            chat_client=object(),
            rag_factory=lambda **kwargs: fake_rag,
        )
        engine.rag = fake_rag  # initialize() faria isso em produção
        assert await engine.adelete_doc_by_filename("b.txt") is True
        assert await engine.adelete_doc_by_filename("nao-existe.txt") is True

    asyncio.run(_run())
    assert fake_rag.deleted == ["doc-aaa"]  # processado (doc-bbb) preservado


def test_engine_adelete_returns_false_on_failure(monkeypatch, tmp_path):
    _settings(monkeypatch, tmp_path)
    settings = deps.get_settings()
    _write_doc_status(settings.storage_dir)
    fake_rag = _FakeRag(fail_ids={"doc-aaa"})

    async def _run():
        engine = LightRAGEngine(
            settings=settings,
            ollama_client=object(),
            chat_client=object(),
            rag_factory=lambda **kwargs: fake_rag,
        )
        engine.rag = fake_rag  # initialize() faria isso em produção
        assert await engine.adelete_doc_by_filename("b.txt") is False

    asyncio.run(_run())


def test_engine_get_doc_status_by_filename(monkeypatch, tmp_path):
    _settings(monkeypatch, tmp_path)
    settings = deps.get_settings()
    _write_doc_status(settings.storage_dir)

    async def _run():
        engine = LightRAGEngine(
            settings=settings,
            ollama_client=object(),
            chat_client=object(),
            rag_factory=lambda **kwargs: _FakeRag(),
        )
        assert await engine.get_doc_status_by_filename("b.txt") == "processing"
        assert await engine.get_doc_status_by_filename("a.txt") == "processed"
        assert await engine.get_doc_status_by_filename("nao-existe.txt") is None

    asyncio.run(_run())
