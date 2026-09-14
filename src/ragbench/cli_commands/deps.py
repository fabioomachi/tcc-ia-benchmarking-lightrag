"""Dependências compartilhadas dos comandos CLI.

`get_settings()` é o ponto único de acesso às configurações — testes fazem
`monkeypatch.setattr(deps, "get_settings", ...)` para isolar do `.env`/singleton.
"""

from rich.console import Console

from ragbench.config import BenchmarkSettings
from ragbench.config import get_settings as global_get_settings

console = Console()


def get_settings() -> BenchmarkSettings:
    """Retorna as configurações efetivas (singleton global por padrão)."""
    return global_get_settings()
