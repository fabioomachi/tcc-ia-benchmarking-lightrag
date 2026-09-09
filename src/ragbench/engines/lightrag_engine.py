import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import numpy as np
from lightrag import LightRAG, QueryParam
from lightrag.prompt import PROMPTS
from lightrag.utils import EmbeddingFunc

from ragbench.config import BenchmarkSettings
from ragbench.config import settings as global_settings
from ragbench.core.models import SearchMode
from ragbench.infrastructure.ollama_client import ResilientOllamaClient

logger = logging.getLogger("ragbench.engine.lightrag")

# Injeção de Ontologia Bancária + Few-Shot Prompting no LightRAG
BANKING_COMPLIANCE_ENTITY_EXTRACTION = (
    "\n\nCRITICAL DOMAIN INSTRUCTION (BANKING COMPLIANCE):\n"
    "You are a banking compliance auditor. Focus exhaustively on extracting entities and relationships "
    "that represent business rules, regulatory constraints, and operational systems.\n"
    "Use strict entity types such as: REGRA_BACEN, PROCEDIMENTO, SISTEMA, CONDICAO, EXCECAO, ATOR, DOCUMENTO, PRAZO.\n"
    "Ignore generic words. Focus heavily on dependencies (e.g., 'requires', 'blocks', 'authorizes').\n\n"
    "### EXAMPLE ###\n"
    "Text: 'O operador deve acionar o bloqueio no MED em até 30 minutos.'\n"
    'Entities: ("operador"$$"ATOR") | ("bloqueio"$$"PROCEDIMENTO") | ("MED"$$"SISTEMA") | ("30 minutos"$$"PRAZO")\n'
    'Relationships: ("operador"$$"bloqueio"$$"ACIONA") | ("bloqueio"$$"MED"$$"REALIZADO_EM") | ("bloqueio"$$"30 minutos"$$"REQUER_PRAZO")\n'
    "###############\n"
)


class LightRAGEngine:
    """Adaptador de alto desempenho para o motor LightRAG com inferência via Ollama."""

    def __init__(
        self,
        settings: BenchmarkSettings | None = None,
        ollama_client: ResilientOllamaClient | None = None,
    ):
        self.settings = settings or global_settings
        self.ollama_client = ollama_client or ResilientOllamaClient(self.settings.ollama)
        self.rag: LightRAG | None = None
        self._inject_prompts()

    def _inject_prompts(self) -> None:
        """Injeta a ontologia bancária nos prompts internos do LightRAG."""
        prompt_base = PROMPTS.get("entity_extraction", "")
        if "BANKING COMPLIANCE" not in prompt_base:
            PROMPTS["entity_extraction"] = prompt_base + BANKING_COMPLIANCE_ENTITY_EXTRACTION

    async def _custom_llm_func(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list | None = None,
        **kwargs: Any,
    ) -> Any:
        language_constraint = (
            "DIRETRIZES OBRIGATÓRIAS:\n"
            "1. Responda SEMPRE e EXCLUSIVAMENTE em Português do Brasil (pt-BR).\n"
            "2. Seja direto e objetivo.\n"
            "3. Responda estritamente com base nos fatos fornecidos no contexto."
        )
        final_sys_prompt = (
            f"{system_prompt}\n\n{language_constraint}" if system_prompt else language_constraint
        )

        messages = [{"role": "system", "content": final_sys_prompt}]
        if history_messages:
            messages.extend(history_messages)
        messages.append({"role": "user", "content": prompt})

        stream = kwargs.get("stream", False)
        return await self.ollama_client.generate_completion(
            model=self.settings.lightrag.llm_model,
            messages=messages,
            temperature=0.0,
            stream=stream,
            **kwargs,
        )

    async def _custom_embedding_func(self, texts: list[str]) -> np.ndarray:
        return await self.ollama_client.get_embeddings(
            model=self.settings.lightrag.embed_model,
            texts=texts,
        )

    async def initialize(self) -> None:
        """Prepara o diretório de armazenamento e inicializa o LightRAG."""
        storage_path = Path(self.settings.storage_dir).resolve()
        storage_path.mkdir(parents=True, exist_ok=True)

        self.rag = LightRAG(
            working_dir=str(storage_path),
            llm_model_func=self._custom_llm_func,
            embedding_func=EmbeddingFunc(
                embedding_dim=self.settings.lightrag.embed_dim,
                max_token_size=8192,
                func=self._custom_embedding_func,
            ),
            chunk_token_size=self.settings.lightrag.chunk_token_size,
            chunk_overlap_token_size=self.settings.lightrag.chunk_overlap_token_size,
            addon_params={"llm_func_timeout": self.settings.lightrag.llm_func_timeout},
        )
        await self.rag.initialize_storages()
        logger.info(f"LightRAG inicializado com sucesso em {storage_path}")

    async def aquery(
        self,
        query: str,
        mode: SearchMode | str = SearchMode.HYBRID,
        top_k: int = 5,
        stream: bool = False,
    ) -> str | AsyncGenerator[str, None]:
        """Executa consulta contra o grafo e vetores do LightRAG."""
        if not self.rag:
            raise RuntimeError("Motor LightRAG não foi inicializado. Chame initialize() primeiro.")

        mode_str = mode.value if isinstance(mode, SearchMode) else str(mode)
        param = QueryParam(mode=mode_str, top_k=top_k, stream=stream)
        return await self.rag.aquery(query, param=param)

    async def ainsert(self, text: str) -> None:
        """Insere conteúdo textual no grafo."""
        if not self.rag:
            raise RuntimeError("Motor LightRAG não foi inicializado.")
        await self.rag.ainsert(text)

    async def finalize(self) -> None:
        """Encerra e persiste storages."""
        if self.rag:
            await self.rag.finalize_storages()
            logger.info("Storages do LightRAG finalizados com segurança.")
