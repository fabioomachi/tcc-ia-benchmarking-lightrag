from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OllamaSettings(BaseModel):
    """Configurações da API local do Ollama."""

    base_url: str = "http://localhost:11434/v1/"
    api_key: str = "ollama_local"
    request_timeout: float = 600.0
    max_retries: int = 3


class LightRAGSettings(BaseModel):
    """Configurações do motor LightRAG."""

    llm_model: str = "qwen2.5:3b"
    embed_model: str = "all-minilm"
    embed_dim: int = 384
    chunk_token_size: int = 512
    chunk_overlap_token_size: int = 128
    llm_func_timeout: int = 600
    default_mode: str = "hybrid"
    default_top_k: int = 5


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
    ragas: RagasSettings = Field(default_factory=RagasSettings)

    # Hiperparâmetros de execução
    concurrency_limit: int = 10
    cache_threshold: float = 0.92
    history_turns: int = 3

    # Caminhos do projeto
    base_dir: Path = Field(default_factory=lambda: Path.cwd())
    pops_dir: Path = Field(default_factory=lambda: Path("entradas/pops"))
    questions_dir: Path = Field(default_factory=lambda: Path("entradas/perguntas"))
    storage_dir: Path = Field(default_factory=lambda: Path("lightrag_ollama_db"))
    runs_dir: Path = Field(default_factory=lambda: Path("runs"))
    logs_dir: Path = Field(default_factory=lambda: Path("logs"))
    result_dir: Path = Field(default_factory=lambda: Path("resultados"))

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
        if not self.logs_dir.is_absolute():
            self.logs_dir = self.base_dir / self.logs_dir
        if not self.result_dir.is_absolute():
            self.result_dir = self.base_dir / self.result_dir


# Singleton acessível por padrão
settings = BenchmarkSettings()
settings.resolve_paths()
