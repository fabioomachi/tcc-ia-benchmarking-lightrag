"""Centralização de logs em `logs/`."""

import logging
import os

from typer.testing import CliRunner

from ragbench.cli import app
from ragbench.cli_commands import deps
from ragbench.config import BenchmarkSettings
from ragbench.infrastructure.logging import (
    get_logger,
    reset_logging_for_tests,
    setup_logging,
)


def _settings(tmp_path, monkeypatch) -> BenchmarkSettings:
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__", "LOGGING__")):
            monkeypatch.delenv(key, raising=False)
    settings = BenchmarkSettings(_env_file=None)
    settings.logging.dir = tmp_path / "logs"
    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    return settings


def test_setup_logging_cria_arquivo(tmp_path, monkeypatch):
    reset_logging_for_tests()
    try:
        settings = _settings(tmp_path, monkeypatch)
        log_file = setup_logging(settings)
        assert log_file == tmp_path / "logs" / "ragbench.log"
        assert log_file.exists()

        get_logger("ragbench.runner").info("mensagem de teste")
        assert "mensagem de teste" in log_file.read_text(encoding="utf-8")
    finally:
        reset_logging_for_tests()


def test_setup_logging_idempotente(tmp_path, monkeypatch):
    reset_logging_for_tests()
    try:
        settings = _settings(tmp_path, monkeypatch)
        setup_logging(settings)
        setup_logging(settings)

        from logging.handlers import RotatingFileHandler

        root = logging.getLogger()
        targets = [
            h
            for h in root.handlers
            if isinstance(h, RotatingFileHandler)
            and h.baseFilename == str((tmp_path / "logs" / "ragbench.log").resolve())
        ]
        assert len(targets) == 1
    finally:
        reset_logging_for_tests()


def test_setup_logging_per_run(tmp_path, monkeypatch):
    reset_logging_for_tests()
    try:
        settings = _settings(tmp_path, monkeypatch)
        setup_logging(settings, run_id="run_teste")
        assert (tmp_path / "logs" / "run_teste.log").exists()
    finally:
        reset_logging_for_tests()


def test_cli_cria_log_global(tmp_path, monkeypatch):
    import ragbench.cli_commands.health as health_mod

    reset_logging_for_tests()
    try:
        _settings(tmp_path, monkeypatch)

        class _FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def check_health(self) -> bool:
                return True

        monkeypatch.setattr(health_mod, "ResilientOllamaClient", _FakeClient)
        result = CliRunner().invoke(app, ["health"])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "logs" / "ragbench.log").exists()
    finally:
        reset_logging_for_tests()


def test_logs_dir_resolvido_para_base_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__", "LOGGING__")):
            monkeypatch.delenv(key, raising=False)
    settings = BenchmarkSettings(_env_file=None)
    settings.resolve_paths()
    assert settings.logging.dir.is_absolute()
    assert str(tmp_path) in str(settings.logging.dir)
