from collections.abc import AsyncGenerator
from typing import Protocol

import numpy as np

from ragbench.core.models import QueryExecutionRecord, SearchMode


class BaseRAGPipeline(Protocol):
    """Contrato comum para qualquer motor de RAG avaliado no benchmark."""

    async def initialize(self) -> None:
        """Prepara storages, índices e conexões."""
        ...

    async def aquery(
        self,
        query: str,
        mode: SearchMode = SearchMode.HYBRID,
        top_k: int = 5,
        stream: bool = False,
    ) -> str | AsyncGenerator[str, None]:
        """Executa a recuperação e geração assíncrona."""
        ...

    async def ainsert(self, text: str) -> None:
        """Insere e indexa um documento no motor."""
        ...

    async def finalize(self) -> None:
        """Libera storages e encerra conexões."""
        ...


class BaseCache(Protocol):
    """Contrato abstrato para implementações de cache."""

    def get(self, query_emb: np.ndarray) -> tuple[str | None, float]:
        """Recupera item em caso de similaridade acima do limiar."""
        ...

    def add(self, query_emb: np.ndarray, response: str) -> None:
        """Adiciona item ao cache."""
        ...


class BaseExecutionStorage(Protocol):
    """Contrato para persistência e checkpointing de execuções de lote."""

    def save_record(self, record: QueryExecutionRecord) -> None:
        """Grava registro atômico de execução."""
        ...

    def get_completed_indices(self) -> set[int]:
        """Retorna os índices das perguntas já concluídas para suporte a --resume."""
        ...

    def load_all_records(self) -> list[QueryExecutionRecord]:
        """Carrega todos os registros persistidos."""
        ...
