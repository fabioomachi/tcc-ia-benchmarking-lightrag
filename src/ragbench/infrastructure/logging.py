"""Centralização de logs em arquivo (`logs/`).

Adapter de infraestrutura: configura o `logging` padrão uma única vez por
processo (idempotente) para que todo log — `ragbench.*` e terceiros
(`lightrag`, `httpx`, `openai`, `ragas`) — seja persistido em `logs/`.

Uso:
    settings = get_settings()
    setup_logging(settings)  # global: logs/ragbench.log
    setup_logging(settings, run_id="run_...")  # extra: logs/<run_id>.log
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ragbench.config import BenchmarkSettings

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

# Arquivos já configurados nesta sessão (idempotência).
_configured_files: set[str] = set()

# Loggers de terceiros ruidosos: mantém em WARNING salvo se nível for DEBUG.
_NOISY_LOGGERS = ("httpx", "httpcore", "openai", "urllib3")


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger padronizado do projeto."""
    return logging.getLogger(name)


def _resolve_level(level_name: str) -> int:
    return logging.getLevelName(level_name.upper().strip() or "INFO")


def _has_file_handler(logger: logging.Logger, target: Path) -> bool:
    for handler in logger.handlers:
        base = getattr(handler, "baseFilename", None)
        if base is not None and Path(base).resolve() == target.resolve():
            return True
    return False


def _ensure_file_handler(
    logger: logging.Logger, log_file: Path, level: int, max_bytes: int, backup_count: int
) -> None:
    if _has_file_handler(logger, log_file):
        return
    handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    _configured_files.add(str(log_file.resolve()))


def reset_logging_for_tests() -> None:
    """Remove handlers de arquivo gerenciados (uso em testes)."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        base = getattr(handler, "baseFilename", None)
        if base is not None and str(Path(base).resolve()) in _configured_files:
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
    _configured_files.clear()


def setup_logging(settings: BenchmarkSettings, run_id: str | None = None) -> Path:
    """Configura o logging em `logs/` de forma idempotente.

    Retorna o caminho do arquivo principal. Nunca levanta exceção para
    não quebrar o CLI em ambientes sem permissão de escrita.
    """
    try:
        return _setup_logging(settings, run_id=run_id)
    except Exception:
        return settings.logging.dir / settings.logging.file_name


def _setup_logging(settings: BenchmarkSettings, run_id: str | None = None) -> Path:
    logs_dir: Path = settings.logging.dir
    logs_dir.mkdir(parents=True, exist_ok=True)

    level = _resolve_level(settings.logging.level)
    main_log = logs_dir / settings.logging.file_name

    # Isolamento entre testes: cada `tmp_path` gera um `logs/` distinto.
    if "PYTEST_CURRENT_TEST" in os.environ:
        active = {str(main_log.resolve())}
        if run_id and settings.logging.per_run_file:
            active.add(str((logs_dir / f"{run_id}.log").resolve()))
        if not active.issubset(_configured_files):
            reset_logging_for_tests()

    if settings.logging.capture_warnings:
        logging.captureWarnings(True)

    root = logging.getLogger()
    root.setLevel(min(root.level or level, level) if root.level else level)
    if root.level == logging.NOTSET or level < root.level:
        root.setLevel(level)

    _ensure_file_handler(
        root, main_log, level, settings.logging.max_bytes, settings.logging.backup_count
    )

    # Handler de console enxuto: arquivo recebe tudo, console só WARNING+.
    if not any(
        isinstance(h, logging.StreamHandler) and getattr(h, "baseFilename", None) is None
        for h in root.handlers
    ):
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(logging.WARNING)
        console.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(console)

    # Hierarquia ragbench propaga para o root (arquivo global).
    ragbench_logger = logging.getLogger("ragbench")
    ragbench_logger.setLevel(level)

    for noisy in _NOISY_LOGGERS:
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))

    if run_id and settings.logging.per_run_file:
        per_run_log = logs_dir / f"{run_id}.log"
        _ensure_file_handler(
            root,
            per_run_log,
            level,
            settings.logging.max_bytes,
            settings.logging.backup_count,
        )

    return main_log
