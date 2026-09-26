"""Não-vazamento de credenciais: SecretStr, scrub de logs e config-check."""

import logging
import os

from pydantic import SecretStr
from typer.testing import CliRunner

from ragbench.cli import app
from ragbench.cli_commands import deps
from ragbench.config import BenchmarkSettings, OllamaSettings
from ragbench.infrastructure.secrets import SecretScrubFilter, redact_key, scrub_text

FAKE_KEY = "AIzaFakeKey123456789012345678901234567"


def _settings(monkeypatch, tmp_path) -> BenchmarkSettings:
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OLLAMA__API_KEY", FAKE_KEY)
    settings = BenchmarkSettings(_env_file=None)
    settings.pops_dir = tmp_path / "pops"
    settings.storage_dir = tmp_path / "graph"
    settings.runs_dir = tmp_path / "runs"
    settings.results_dir = tmp_path / "resultados"
    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    return settings


def test_api_key_is_secret_str():
    settings = OllamaSettings(api_key=FAKE_KEY)
    assert isinstance(settings.api_key, SecretStr)
    assert settings.api_key.get_secret_value() == FAKE_KEY


def test_repr_and_dump_never_expose_key():
    settings = OllamaSettings(api_key=FAKE_KEY)
    assert FAKE_KEY not in repr(settings)
    assert FAKE_KEY not in str(settings.model_dump())
    assert FAKE_KEY not in settings.model_dump_json()


def test_redact_key_shows_presence_only():
    assert FAKE_KEY not in redact_key(SecretStr(FAKE_KEY))
    assert "definida" in redact_key(SecretStr(FAKE_KEY))
    assert redact_key(SecretStr("")) == "ausente"
    assert redact_key(None) == "ausente"


def test_scrub_text_removes_google_key_and_header():
    dirty = f"erro em https://x?key={FAKE_KEY} com header x-goog-api-key: {FAKE_KEY}"
    clean = scrub_text(dirty)
    assert FAKE_KEY not in clean
    assert scrub_text("nada sensivel aqui") == "nada sensivel aqui"


def test_log_filter_scrubs_record():
    filt = SecretScrubFilter()
    record = logging.LogRecord(
        name="t",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=f"falha com {FAKE_KEY}",
        args=(),
        exc_info=None,
    )
    assert filt.filter(record) is True
    assert FAKE_KEY not in str(record.msg)


def test_config_check_never_prints_key(monkeypatch, tmp_path):
    _settings(monkeypatch, tmp_path)
    result = CliRunner().invoke(app, ["config-check"])
    assert result.exit_code == 0, result.output
    assert FAKE_KEY not in result.output
    assert "definida" in result.output
    assert "gemini" in result.output
