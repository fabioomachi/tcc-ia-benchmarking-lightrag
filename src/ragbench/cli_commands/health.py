"""Comando `health`: conectividade do transporte Gemini e fallback local."""

import asyncio
import sys

from ragbench.cli_commands import deps
from ragbench.infrastructure.ollama_client import OllamaChatClient, ResilientOllamaClient


def check_health() -> None:
    """Verifica a conectividade com o transporte Gemini e o fallback local."""
    settings = deps.get_settings()
    index_client = ResilientOllamaClient(settings.ollama)
    index_up = asyncio.run(index_client.check_health())

    # Transporte unificado: chat usa o mesmo pipeline Gemini do index.
    # Só checa Ollama local se o modelo de chat NÃO for Gemini.
    chat_model = settings.chat.llm_model or ""
    if chat_model.startswith("gemini-"):
        chat_up = index_up
        chat_target = f"Gemini ({chat_model}) via {settings.ollama.base_url}"
    else:
        chat_client = OllamaChatClient(settings.chat)
        chat_up = asyncio.run(chat_client.check_health())
        chat_target = settings.chat.base_url
    if index_up and chat_up:
        deps.console.print(
            "[green]✔ Index "
            f"({settings.lightrag.llm_model}) e Chat ({chat_model}) operacionais.[/green]"
        )
    else:
        if not index_up:
            deps.console.print(f"[red]✖ Falha no index em {settings.ollama.base_url}[/red]")
        if not chat_up:
            deps.console.print(f"[red]✖ Falha no chat em {chat_target}[/red]")
        sys.exit(1)
