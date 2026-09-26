"""Comando `config-check`: exibe a configuração efetiva sem expor segredos.

Substitui a inspeção manual do `.env` (que vaza a chave no terminal): valores
de `api_key` aparecem apenas como presença/tamanho, nunca o valor.
"""

from ragbench.cli_commands import deps
from ragbench.infrastructure.secrets import redact_key


def check_config() -> None:
    """Mostra modelos, embeddings, diretórios e presença da chave API."""
    settings = deps.get_settings()
    console = deps.console
    console.print("[bold blue]Configuração efetiva (segredos redigidos)[/bold blue]")
    console.print(
        f"  index:  [cyan]{settings.lightrag.llm_model}[/cyan] (+embeddings "
        f"{settings.lightrag.embed_model}/{settings.lightrag.embed_dim})"
    )
    console.print(f"  chat:   [cyan]{settings.chat.llm_model}[/cyan]")
    console.print(f"  juiz:   [cyan]{settings.ragas.judge_model}[/cyan]")
    console.print(f"  api endpoint: [cyan]{settings.ollama.base_url}[/cyan]")
    console.print(f"  api key: [cyan]{redact_key(settings.ollama.api_key)}[/cyan]")
    console.print(f"  pops:   {settings.pops_dir}")
    console.print(f"  grafo:  {settings.storage_dir}")
    console.print(f"  runs:   {settings.runs_dir}")
    console.print(
        f"  concorrência: {settings.concurrency_limit} | "
        f"cache_threshold: {settings.cache_threshold}"
    )
