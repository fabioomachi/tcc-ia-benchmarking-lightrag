"""Comando `chat`: sessão interativa com streaming, cache e telemetria."""

import asyncio
import sys
import time
from typing import Annotated

import typer
from rich.panel import Panel

from ragbench.cli_commands import deps
from ragbench.config import BenchmarkSettings
from ragbench.core.exceptions import OllamaConnectionError
from ragbench.core.models import SearchMode
from ragbench.engines.lightrag_engine import LightRAGEngine
from ragbench.infrastructure.semantic_cache import SemanticCache, SlidingWindowHistory


def apply_chat_model_override(
    settings: BenchmarkSettings, chat_model: str | None
) -> BenchmarkSettings:
    """Aplica o override do modelo sem mutar o objeto original (retorna cópia)."""
    if not chat_model:
        return settings
    override = settings.model_copy(deep=True)
    override.chat.llm_model = chat_model
    return override


def interactive_chat(
    mode: Annotated[str, typer.Option(help="Modo de busca")] = "hybrid",
    top_k: Annotated[int, typer.Option(help="Top-K entidades")] = 5,
    chat_model: Annotated[str | None, typer.Option(help="Override do modelo de chat")] = None,
) -> None:
    """Sessão conversacional interativa (transporte Gemini, modelo de chat dedicado).

    Espelha a robustez do `index`: inicializa/finaliza storages com segurança,
    usa o mesmo pipeline resiliente do index (rate-limit + retries + streaming
    via `ResilientOllamaClient`), mas gera com `CHAT__LLM_MODEL`
    (ex: `gemini-3.1-flash-lite`) — diferenciado de `LIGHTRAG__LLM_MODEL`.
    Embeddings de consulta e cache seguem a fonte única do index.
    """
    settings = apply_chat_model_override(deps.get_settings(), chat_model)
    search_mode = SearchMode(mode)
    cache = SemanticCache(threshold=settings.cache_threshold)
    history = SlidingWindowHistory(max_turns=settings.history_turns)

    async def _chat_loop():
        engine = LightRAGEngine.for_chat(settings=settings)
        await engine.initialize()

        try:
            deps.console.print(
                Panel(
                    "[bold green]ragbench Interactive Chat[/bold green]\n"
                    f"Modo: [cyan]{mode}[/cyan] | Top-K: [cyan]{top_k}[/cyan]\n"
                    f"Chat LLM: [cyan]{engine.llm_model}[/cyan] "
                    f"(index: [dim]{settings.lightrag.llm_model}[/dim])\n"
                    f"Embed: [cyan]{settings.lightrag.embed_model}[/cyan] "
                    f"dim={settings.lightrag.embed_dim} (fonte única: index)\n"
                    "Transporte: [cyan]Gemini resiliente[/cyan] "
                    f"| Histórico: {settings.history_turns} turnos\n"
                    "Digite [bold red]'sair'[/bold red] para encerrar.",
                    title="Sessão Iniciada",
                )
            )

            while True:
                try:
                    query = deps.console.input("\n[bold yellow]Pergunta > [/bold yellow]").strip()
                    if query.lower() in ["sair", "exit", "quit"]:
                        break
                    if not query:
                        continue

                    start_time = time.perf_counter()

                    # 1. Embeddings pela fonte única (index/Gemini) — como no index.
                    query_embs = await engine.get_query_embeddings([query])
                    if len(query_embs) > 0:
                        cached_resp, similarity = cache.get(query_embs[0])
                        if cached_resp:
                            latency = time.perf_counter() - start_time
                            deps.console.print(
                                "\n[green]⚡ Resposta (via Cache Semântico - "
                                f"Score: {similarity:.3f} | Latência: {latency:.3f}s):[/green]"
                            )
                            deps.console.print(cached_resp)
                            history.add_turn(query, cached_resp)
                            continue

                    # 2. RAG com streaming + histórico (QueryParam), mesmo
                    # transporte resiliente do index, modelo do chat.
                    deps.console.print(
                        f"\n[blue]🤖 Resposta Gerada ({mode} | {engine.llm_model}):[/blue]"
                    )
                    response_gen = await engine.aquery(
                        query,
                        mode=search_mode,
                        top_k=top_k,
                        stream=True,
                        history_messages=history.get_messages(),
                    )

                    first_token = True
                    ttft = 0.0
                    full_text = ""

                    if isinstance(response_gen, str):
                        ttft = time.perf_counter() - start_time
                        full_text = response_gen
                        deps.console.print(full_text)
                    else:
                        async for chunk in response_gen:
                            if first_token:
                                ttft = time.perf_counter() - start_time
                                first_token = False
                            sys.stdout.write(chunk)
                            sys.stdout.flush()
                            full_text += chunk
                        if first_token:  # stream vazio
                            ttft = time.perf_counter() - start_time

                    total_latency = time.perf_counter() - start_time
                    deps.console.print(
                        f"\n\n[dim]⏱ Latência Total: {total_latency:.3f}s | TTFT: {ttft:.3f}s "
                        f"| Modelo: {engine.llm_model}[/dim]"
                    )

                    if full_text.strip():
                        if len(query_embs) > 0:
                            cache.add(query_embs[0], full_text)
                        history.add_turn(query, full_text)

                except KeyboardInterrupt:
                    break
                except OllamaConnectionError as e:
                    deps.console.print(
                        f"[red]Falha resiliente esgotada (rate-limit/rede): {e}[/red]\n"
                        "[yellow]Aguarde a janela de rate-limit e tente novamente.[/yellow]"
                    )
                except Exception as e:
                    deps.console.print(f"[red]Erro no processamento: {e}[/red]")
        finally:
            await engine.finalize()
            deps.console.print("[yellow]Sessão encerrada com sucesso.[/yellow]")

    asyncio.run(_chat_loop())
