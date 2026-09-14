from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OllamaSettings(BaseModel):
    """Configurações da API local do Ollama / Gemini."""

    base_url: str = "http://localhost:11434/v1/"
    api_key: str = "ollama_local"
    request_timeout: float = 900.0
    max_retries: int = 3
    connect_timeout: float = 10.0

    # Rate-limit entre requisições de completion
    rate_limit_interval_seconds: float = 4.2

    # Completion / retry
    completion_max_attempts: int = 6
    completion_max_tokens: int = 8192
    completion_default_temperature: float = 0.0
    retry_initial_delay: float = 5.0
    retry_backoff_factor: float = 2.0
    retry_max_delay: float = 60.0
    retry_backoff: float = 3.0
    retry_jitter_min: float = 2.0

    # Embeddings via REST
    embedding_api_base_url: str = "https://generativelanguage.googleapis.com/v1beta/models"
    embedding_api_model: str = "gemini-embedding-001"
    embedding_default_dim: int = 768
    embedding_max_concurrency: int = 3
    embedding_max_attempts: int = 3
    embedding_timeout: float = 10.0
    embedding_retry_delay: float = 2.0
    embedding_retry_short_delay: float = 1.0
    embedding_batch_size: int = 5
    embedding_micro_pause: float = 0.3


class LightRAGSettings(BaseModel):
    """Configurações do motor LightRAG."""

    llm_model: str = "qwen2.5:1.5b"
    embed_model: str = "all-minilm"
    embed_dim: int = 384
    chunk_token_size: int = 1500
    chunk_overlap_token_size: int = 128
    llm_func_timeout: int = 600
    default_mode: str = "hybrid"
    default_top_k: int = 5
    # LLM custom func
    llm_temperature: float = 0.0
    llm_max_token_size: int = 8192
    embedding_max_token_size: int = 16384
    # Inicialização do LightRAG — INDEX (config testada, Gemini)
    default_llm_timeout: int = 2400
    llm_model_max_async: int = 1
    embedding_func_timeout: int = 600
    embedding_func_max_async: int = 1
    language: str = "Portuguese"
    # Workers do CHAT (Ollama local) — usados quando role="chat".
    # Local aguenta mais concorrência que a API Gemini (rate-limit),
    # mas com timeouts menores pois a resposta é interativa.
    chat_default_llm_timeout: int = 2400
    chat_llm_model_max_async: int = 16
    chat_llm_func_timeout: int = 600
    chat_embedding_func_timeout: int = 600
    chat_embedding_func_max_async: int = 8


class ChatSettings(BaseModel):
    """Configurações do LLM de chat/query.

    Arquitetura unificada (pós-refactor): o transporte LLM do chat é o MESMO
    pipeline resiliente do index (`ResilientOllamaClient` via Gemini
    OpenAI-compatível, com rate-limit + retries + streaming). A diferenciação
    entre index e chat é APENAS no nome do modelo:

    - index → `lightrag.llm_model` (`LIGHTRAG__LLM_MODEL`)
    - chat  → `chat.llm_model` (`CHAT__LLM_MODEL`, ex: `gemini-3.1-flash-lite`)

    Os embeddings são SEMPRE os do index (`lightrag.embed_*/768` via Gemini)
    — dois modelos distintos de embedding quebram o retrieval, por isso
    `embed_model/embed_dim` aqui são apenas espelho documentado e devem
    igualar `lightrag.embed_*`.

    `base_url/api_key` legados do Ollama local são mantidos para fallback
    manual, mas o caminho padrão do `LightRAGEngine(role="chat")` reutiliza
    `settings.ollama` (Gemini) como transporte.
    """

    base_url: str = "http://localhost:11434/v1/"
    api_key: str = "ollama"
    llm_model: str = "gemini-3.1-flash-lite"
    embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768
    temperature: float = 0.0
    max_tokens: int = 8192
    num_ctx: int = 8192
    request_timeout: float = 900.0
    max_retries: int = 3
    connect_timeout: float = 10.0


class RagasSettings(BaseModel):
    """Configurações do LLM-as-a-Judge (RAGAS).

    Arquitetura unificada: o juiz usa o MESMO transporte Gemini do
    index/chat (endpoint OpenAI-compatível em `ollama.base_url` + `api_key`).
    A diferenciação é SÓ no modelo: `ragas.judge_model` (`RAGAS__JUDGE_MODEL`,
    ex: `gemini-3.8-flash`) ≠ `lightrag.llm_model` ≠ `chat.llm_model`.
    Modelos sem prefixo `gemini-` mantêm fallback Ollama local.
    """

    judge_model: str = "gemini-3.8-flash"
    embed_model: str = "gemini-embedding-001"
    num_ctx: int = 8192
    timeout: int = 1200
    max_workers: int = 1
    # Resiliência contra 429/503 transitórios do Gemini (picos de demanda).
    # judge_max_retries: retries rápidos no cliente; run_max_*: retries com
    # backoff exponencial no nível do RAGAS (RunConfig/tenacity).
    judge_max_retries: int = 8
    run_max_retries: int = 15
    run_max_wait: int = 180


class BenchmarkSettings(BaseSettings):
    """Configurações globais e orquestração do benchmark."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Sub-configurações
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    lightrag: LightRAGSettings = Field(default_factory=LightRAGSettings)
    chat: ChatSettings = Field(default_factory=ChatSettings)
    ragas: RagasSettings = Field(default_factory=RagasSettings)

    # Hiperparâmetros de execução
    concurrency_limit: int = 10
    cache_threshold: float = 0.92
    history_turns: int = 3

    # Caminhos do projeto
    base_dir: Path = Field(default_factory=lambda: Path.cwd())
    pops_dir: Path = Field(default_factory=lambda: Path("data/pops"))
    questions_dir: Path = Field(default_factory=lambda: Path("data"))
    storage_dir: Path = Field(default_factory=lambda: Path("lightrag_ollama_db"))
    runs_dir: Path = Field(default_factory=lambda: Path("runs"))
    results_dir: Path = Field(default_factory=lambda: Path("resultados"))

    def resolve_paths(self) -> None:
        """Assegura caminhos absolutos relativos ao base_dir."""
        if not self.pops_dir.is_absolute():
            self.pops_dir = self.base_dir / self.pops_dir
        if not self.questions_dir.is_absolute():
            self.questions_dir = self.base_dir / self.questions_dir
        if not self.storage_dir.is_absolute():
            self.storage_dir = self.base_dir / self.storage_dir
        if not self.runs_dir.is_absolute():
            self.runs_dir = self.base_dir / self.runs_dir
        if not self.results_dir.is_absolute():
            self.results_dir = self.base_dir / self.results_dir


# Singleton preguiçoso: importar o módulo não lê mais o .env nem toca o cwd.
# O primeiro acesso (via get_settings() ou `config.settings`) constrói e resolve.
_cached_settings: BenchmarkSettings | None = None


def get_settings() -> BenchmarkSettings:
    """Retorna o singleton de configurações, construindo-o sob demanda."""
    global _cached_settings
    if _cached_settings is None:
        _cached_settings = BenchmarkSettings()
        _cached_settings.resolve_paths()
    return _cached_settings


def reset_settings_cache() -> None:
    """Descarta o singleton (uso em testes que mudam de diretório/env)."""
    global _cached_settings
    _cached_settings = None


def __getattr__(name: str) -> Any:
    # Compatibilidade: `from ragbench.config import settings` continua válido,
    # mas agora resolve de forma preguiçosa em vez de executar no import.
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
