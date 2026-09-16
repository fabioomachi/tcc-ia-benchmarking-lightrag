"""Motor LLM-direto: mesma LLM/transporte do chat, zero retrieval.

Braço baseline do TCC: isola a contribuição do grafo respondendo só com o
conhecimento geral do modelo (`CHAT__LLM_MODEL` via `ResilientOllamaClient`).
Postura "tentar responder" (sem abstinência forçada) para o RAGAS expor a
alucinação nas regras de domínio; `get_query_embeddings` existe só para o
cache semântico não quebrar o contrato `BaseRAGPipeline`.
"""

from collections.abc import AsyncGenerator

import numpy as np

from ragbench.config import BenchmarkSettings, get_settings
from ragbench.core.models import SearchMode
from ragbench.infrastructure.logging import get_logger
from ragbench.infrastructure.ollama_client import ResilientOllamaClient

logger = get_logger("ragbench.engine.direct")

DIRECT_SYSTEM_PROMPT = (
    "Você é um assistente bancário. Responda SEMPRE em Português do Brasil "
    "(pt-BR), de forma direta, usando seu conhecimento geral. "
    "Você NÃO tem acesso aos documentos internos do banco nesta pergunta: "
    "responda o melhor que puder com conhecimento geral."
)


class DirectLLMEngine:
    """Baseline sem grafo: LLM puro, sem índice, sem vetores, sem chunks."""

    def __init__(
        self,
        settings: BenchmarkSettings | None = None,
        ollama_client: ResilientOllamaClient | None = None,
    ):
        self.settings = settings or get_settings()
        self.ollama_client = ollama_client or ResilientOllamaClient(self.settings.ollama)

    @property
    def llm_model(self) -> str:
        """Modelo efetivo: o mesmo do chat (isola só o retrieval)."""
        return self.settings.chat.llm_model

    async def initialize(self) -> None:
        """Sem storages: nada a preparar (no-op documentado)."""

    async def finalize(self) -> None:
        """Sem storages: nada a liberar (no-op documentado)."""

    async def ainsert(self, text: str) -> None:
        """Baseline não indexa: chamada ignorada com aviso."""
        logger.warning("DirectLLMEngine.ainsert ignorado (baseline sem índice).")

    async def get_query_embeddings(self, texts: list[str]) -> np.ndarray:
        """Embeddings via fonte do index (só para o cache; sem retrieval)."""
        return await self.ollama_client.get_embeddings(
            model=self.settings.lightrag.embed_model,
            embedding_dim=self.settings.lightrag.embed_dim,
            max_token_size=self.settings.lightrag.embedding_max_token_size,
            texts=texts,
        )

    async def aquery(
        self,
        query: str,
        mode: SearchMode | str = SearchMode.HYBRID,
        top_k: int = 5,
        stream: bool = False,
        **kwargs,
    ) -> str | AsyncGenerator[str, None]:
        """Gera resposta direta, sem consultar grafo, vetores ou chunks."""
        messages = [
            {"role": "system", "content": DIRECT_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        return await self.ollama_client.generate_completion(
            model=self.llm_model,
            messages=messages,
            temperature=self.settings.chat.temperature,
            max_tokens=self.settings.chat.max_tokens,
            stream=stream,
        )
