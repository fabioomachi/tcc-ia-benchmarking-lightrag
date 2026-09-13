from pathlib import Path

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
    """Configurações do LLM local de chat/query (Ollama).

    O LLM de geração é local (qwen3.5:4b). Os embeddings são SEMPRE os do
    index (text-embedding-005/768 via Gemini) — dois modelos distintos de
    embedding quebram o retrieval, por isso embed_model/embed_dim aqui são
    apenas espelho documentado e devem igualar lightrag.embed_*.
    """

    base_url: str = "http://localhost:11434/v1/"
    api_key: str = "ollama"
    llm_model: str = "qwen3.5:4b"
    embed_model: str = "text-embedding-005"
    embed_dim: int = 768
    temperature: float = 0.0
    max_tokens: int = 2048
    num_ctx: int = 4096
    request_timeout: float = 900.0
    max_retries: int = 3
    connect_timeout: float = 10.0


class RagasSettings(BaseModel):
    """Configurações do LLM-as-a-Judge (RAGAS)."""

    judge_model: str = "qwen2.5:7b"
    embed_model: str = "nomic-embed-text"
    num_ctx: int = 8192
    timeout: int = 1200
    max_workers: int = 1


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


# Singleton acessível por padrão
settings = BenchmarkSettings()
settings.resolve_paths()
