from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any

import numpy as np
from lightrag import LightRAG, QueryParam
from lightrag.prompt import PROMPTS
from lightrag.utils import EmbeddingFunc

from ragbench.config import BenchmarkSettings, ChatSettings, get_settings
from ragbench.core.models import SearchMode
from ragbench.infrastructure.logging import get_logger
from ragbench.infrastructure.ollama_client import OllamaChatClient, ResilientOllamaClient

logger = get_logger("ragbench.engine.lightrag")

# Injeção de Ontologia Bancária + Few-Shot Prompting no LightRAG
BANKING_COMPLIANCE_ENTITY_EXTRACTION = (
    "\n\nCRITICAL DOMAIN INSTRUCTION (BANKING COMPLIANCE):\n"
    "You are a banking compliance auditor. Focus exhaustively on extracting entities and relationships "
    "that represent business rules, regulatory constraints, and operational systems.\n"
    "Use strict entity types such as: REGRA_BACEN, PROCEDIMENTO, SISTEMA, CONDICAO, EXCECAO, ATOR, DOCUMENTO, PRAZO.\n"
    "Ignore generic words. Focus heavily on dependencies (e.g., 'requires', 'blocks', 'authorizes').\n\n"
    "### EXAMPLE ###\n"
    'Text: "O operador deve acionar o bloqueio no MED em ate 30 minutos."\n'
    '("operador"<|#>"ATOR"<|#>"Operador do sistema responsável por acionar o bloqueio")\n'
    '("MED"<|#>"SISTEMA"<|#>"Sistema do BACEN para devolução cautelar")\n'
    '("operador"<|#>"MED"<|#>"aciona o sistema"<|#>"aciona")\n'
    "###############\n"
)


class _SafeCallable:
    """Wrapper que protege callables contra erros de deepcopy do LightRAG com RLock."""

    def __init__(self, target: Any):
        self.target = target

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.target(*args, **kwargs)

    def __deepcopy__(self, memo: Any) -> Any:
        return self


def build_entity_extraction_prompt(base_prompt: str) -> str:
    """Aplica a ontologia bancária ao prompt base (puro: sem mutar global).

    Idempotente: se o marcador já estiver presente, retorna a base inalterada.
    """
    if "BANKING COMPLIANCE" in base_prompt:
        return base_prompt
    return base_prompt + BANKING_COMPLIANCE_ENTITY_EXTRACTION


def build_llm_messages(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Monta as mensagens do LLM com a restrição de idioma (puro: sem I/O)."""
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
    return messages


class LightRAGEngine:
    """Adaptador dual-model sobre transporte único resiliente (Gemini).

    Ambos os roles usam `ResilientOllamaClient` (endpoint Gemini
    OpenAI-compatível + REST de embeddings, com rate-limit, retries com
    backoff/jitter e streaming). A diferenciação index/chat é SÓ no modelo:

    - role="index": `settings.lightrag.llm_model` (`LIGHTRAG__LLM_MODEL`)
    - role="chat":  `settings.chat.llm_model` (`CHAT__LLM_MODEL`)

    O diretório de armazenamento (grafo) é compartilhado: o index constrói,
    o chat apenas consulta. Embeddings são sempre via index
    (`lightrag.embed_model/embed_dim`) para não quebrar o retrieval.
    O `OllamaChatClient` legado é mantido apenas para `health` fallback local.
    """

    def __init__(
        self,
        settings: BenchmarkSettings | None = None,
        ollama_client: ResilientOllamaClient | None = None,
        chat_client: OllamaChatClient | None = None,
        role: str = "index",
        rag_factory: Callable[..., LightRAG] | None = None,
    ):
        self.settings = settings or get_settings()
        if role not in ("index", "chat"):
            raise ValueError(f"role inválido: {role!r} (use 'index' ou 'chat')")
        self.role = role
        self.ollama_client = ollama_client or ResilientOllamaClient(self.settings.ollama)
        self.chat_client = chat_client or OllamaChatClient(self._chat_settings)
        self._rag_factory = rag_factory or LightRAG
        self.rag: LightRAG | None = None
        self._inject_prompts()
        if role == "chat" and self.settings.chat.embed_dim != self.settings.lightrag.embed_dim:
            logger.warning(
                "chat.embed_dim (%s) != lightrag.embed_dim (%s). "
                "Retrieval pode degradar; alinhe os embeddings se possível.",
                self.settings.chat.embed_dim,
                self.settings.lightrag.embed_dim,
            )

    @property
    def _chat_settings(self) -> ChatSettings:
        return self.settings.chat

    @property
    def llm_model(self) -> str:
        """Modelo LLM efetivo conforme o role (diferenciação index/chat)."""
        if self.role == "chat":
            return self.settings.chat.llm_model
        return self.settings.lightrag.llm_model

    @property
    def llm_temperature(self) -> float:
        """Temperatura efetiva conforme o role."""
        if self.role == "chat":
            return self.settings.chat.temperature
        return self.settings.lightrag.llm_temperature

    @property
    def llm_max_tokens(self) -> int:
        """Max tokens efetivo conforme o role."""
        if self.role == "chat":
            return self.settings.chat.max_tokens
        return self.settings.ollama.completion_max_tokens

    @classmethod
    def for_index(
        cls,
        settings: BenchmarkSettings | None = None,
        ollama_client: ResilientOllamaClient | None = None,
        rag_factory: Callable[..., LightRAG] | None = None,
    ) -> "LightRAGEngine":
        """Engine de indexação (config atual testada / Gemini)."""
        return cls(
            settings=settings, ollama_client=ollama_client, role="index", rag_factory=rag_factory
        )

    @classmethod
    def for_chat(
        cls,
        settings: BenchmarkSettings | None = None,
        ollama_client: ResilientOllamaClient | None = None,
        chat_client: OllamaChatClient | None = None,
        rag_factory: Callable[..., LightRAG] | None = None,
    ) -> "LightRAGEngine":
        """Engine de chat/query (Ollama local, ex: qwen3.5:4b)."""
        return cls(
            settings=settings,
            ollama_client=ollama_client,
            chat_client=chat_client,
            role="chat",
            rag_factory=rag_factory,
        )

    def _inject_prompts(self) -> None:
        """Injeta a ontologia bancária nos prompts internos do LightRAG."""
        prompt_base = PROMPTS.get("entity_extraction", "")
        PROMPTS["entity_extraction"] = build_entity_extraction_prompt(prompt_base)

    async def _custom_llm_func(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list | None = None,
        **kwargs: Any,
    ) -> Any:
        """LLM unificado: mesmo transporte resiliente (Gemini) p/ index e chat.

        Diferencia apenas `model/temperature/max_tokens` via propriedades
        `llm_model/llm_temperature/llm_max_tokens` (role-aware).
        """
        messages = build_llm_messages(prompt, system_prompt, history_messages)

        logger.debug(
            "LLM func role=%s model=%s msg_chars=%d history=%d",
            self.role,
            self.llm_model,
            len(str(messages)),
            len(history_messages or []),
        )

        stream = kwargs.pop("stream", False)
        kwargs.pop("temperature", None)
        kwargs.pop("max_tokens", None)

        try:
            # Transporte único: ResilientOllamaClient (Gemini). O Ollama local
            # (chat_client) NÃO é mais usado para geração — apenas health.
            resp = await self.ollama_client.generate_completion(
                model=self.llm_model,
                messages=messages,
                temperature=self.llm_temperature,
                max_tokens=self.llm_max_tokens,
                stream=stream,
                **kwargs,
            )
            logger.debug("LLM func role=%s resposta chars=%d", self.role, len(repr(resp)))
            return resp
        except Exception:
            logger.exception("Falha no LLM role=%s model=%s", self.role, self.llm_model)
            raise

    async def _custom_embedding_func(self, texts: list[str]) -> np.ndarray:
        # Fonte única de verdade: embeddings sempre via index (Gemini
        # text-embedding-005/768). Usar all-minilm no chat quebraria o
        # retrieval contra vetores já indexados.
        return await self.ollama_client.get_embeddings(
            model=self.settings.lightrag.embed_model,
            embedding_dim=self.settings.lightrag.embed_dim,
            max_token_size=self.settings.lightrag.embedding_max_token_size,
            texts=texts,
        )

    async def initialize(self) -> None:
        """Prepara o diretório de armazenamento e inicializa o LightRAG."""
        storage_path = Path(self.settings.storage_dir).resolve()
        storage_path.mkdir(parents=True, exist_ok=True)

        # Embedding único (index) para index e chat — garante compatibilidade
        # dos vetores de consulta com o grafo já construído.
        embedding_dim = self.settings.lightrag.embed_dim
        embedding_max_token_size = self.settings.lightrag.embedding_max_token_size

        # Workers por role: index usa a config testada (Gemini), chat usa a
        # config local (timeouts menores, mais concorrência).
        if self.role == "chat":
            default_llm_timeout = self.settings.lightrag.chat_default_llm_timeout
            llm_model_max_async = self.settings.lightrag.chat_llm_model_max_async
            llm_func_timeout = self.settings.lightrag.chat_llm_func_timeout
            embedding_func_timeout = self.settings.lightrag.chat_embedding_func_timeout
            embedding_func_max_async = self.settings.lightrag.chat_embedding_func_max_async
        else:
            default_llm_timeout = self.settings.lightrag.default_llm_timeout
            llm_model_max_async = self.settings.lightrag.llm_model_max_async
            llm_func_timeout = self.settings.lightrag.llm_func_timeout
            embedding_func_timeout = self.settings.lightrag.embedding_func_timeout
            embedding_func_max_async = self.settings.lightrag.embedding_func_max_async

        self.rag = self._rag_factory(
            working_dir=str(storage_path),
            default_llm_timeout=default_llm_timeout,
            llm_model_max_async=llm_model_max_async,
            llm_model_func=_SafeCallable(self._custom_llm_func),
            embedding_func=EmbeddingFunc(
                embedding_dim=embedding_dim,
                max_token_size=embedding_max_token_size,
                func=_SafeCallable(self._custom_embedding_func),
            ),
            chunk_token_size=self.settings.lightrag.chunk_token_size,
            chunk_overlap_token_size=self.settings.lightrag.chunk_overlap_token_size,
            addon_params={
                "llm_func_timeout": llm_func_timeout,
                "language": self.settings.lightrag.language,
                "embedding_func_timeout": embedding_func_timeout,
                "embedding_func_max_async": embedding_func_max_async,
            },
        )
        if hasattr(self.rag, "initialize_storages"):
            await self.rag.initialize_storages()
        logger.info(f"LightRAG inicializado com sucesso em {storage_path}")

    async def get_query_embeddings(self, texts: list[str]) -> np.ndarray:
        """Embeddings de consulta (sempre via index: text-embedding-005/768)."""
        return await self._custom_embedding_func(texts)

    async def aquery(
        self,
        query: str,
        mode: SearchMode | str = SearchMode.HYBRID,
        top_k: int = 5,
        stream: bool = False,
        enable_rerank: bool = False,
        history_messages: list[dict[str, str]] | None = None,
    ) -> str | AsyncGenerator[str, None]:
        """Executa consulta contra o grafo e vetores do LightRAG.

        Espelha o `ainsert` do index em robustez: `stream` e
        `conversation_history` são repassados ao `QueryParam` (antes eram
        aceitos na assinatura e silenciosamente ignorados).
        """
        if not self.rag:
            raise RuntimeError("Motor LightRAG não foi inicializado. Chame initialize() primeiro.")

        mode_str = mode.value if isinstance(mode, SearchMode) else str(mode)
        param = QueryParam(
            mode=mode_str,
            top_k=top_k,
            stream=stream,
            conversation_history=history_messages or [],
            enable_rerank=enable_rerank,
        )
        return await self.rag.aquery(query, param=param)

    async def ainsert(self, text: str) -> None:
        """Insere conteúdo textual no grafo."""
        if not self.rag:
            raise RuntimeError("Motor LightRAG não foi inicializado.")
        await self.rag.ainsert(text)

    async def finalize(self) -> None:
        """Encerra e persiste storages."""
        if self.rag and hasattr(self.rag, "finalize_storages"):
            await self.rag.finalize_storages()
            logger.info("Storages do LightRAG finalizados com segurança.")
