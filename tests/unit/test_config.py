import os

import pytest

import ragbench.config as config_mod
from ragbench.config import BenchmarkSettings, OllamaSettings, get_settings, reset_settings_cache


def test_default_config(tmp_path, monkeypatch):
    # Hermético: `uv run` exporta o .env do repo para o ambiente, então é preciso
    # remover as variáveis (além de ignorar o arquivo .env via chdir + _env_file).
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__")):
            monkeypatch.delenv(key, raising=False)
    settings = BenchmarkSettings(_env_file=None)
    assert settings.ollama.base_url == "http://localhost:11434/v1/"
    assert settings.lightrag.llm_model == "qwen2.5:1.5b"
    assert settings.lightrag.embed_model == "all-minilm"
    assert settings.ragas.judge_model == "gemini-3.8-flash"
    assert settings.concurrency_limit == 10
    assert settings.cache_threshold == 0.92


def test_custom_ollama_settings():
    ollama = OllamaSettings(base_url="http://custom:11434/v1/", request_timeout=30.0)
    assert ollama.base_url == "http://custom:11434/v1/"
    assert ollama.request_timeout == 30.0


@pytest.fixture
def _isolated_cache():
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_get_settings_cached_singleton(_isolated_cache):
    assert get_settings() is get_settings()


def test_get_settings_reset_rebuilds(_isolated_cache):
    first = get_settings()
    reset_settings_cache()
    assert get_settings() is not first


def test_get_settings_resolves_absolute_paths(_isolated_cache):
    settings = get_settings()
    assert settings.pops_dir.is_absolute()
    assert settings.runs_dir.is_absolute()
    assert settings.results_dir.is_absolute()


def test_settings_attr_delegates_to_getter(_isolated_cache):
    assert config_mod.settings is get_settings()


def test_unknown_attr_raises(_isolated_cache):
    with pytest.raises(AttributeError):
        _ = config_mod.nao_existe
