from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class QuestionType(StrEnum):
    """Categorias adversariais e de complexidade para perguntas."""

    EDGE_CASE = "EDGE_CASE"
    REGULATORY_TIMELINE = "REGULATORY_TIMELINE"
    CONDITIONAL_WORKFLOW = "CONDITIONAL_WORKFLOW"
    ROLE_RESTRICTION = "ROLE_RESTRICTION"
    UNMAPPED = "UNMAPPED"


class SearchMode(StrEnum):
    """Estratégias de busca suportadas pelo motor RAG."""

    NAIVE = "naive"
    LOCAL = "local"
    GLOBAL = "global"
    HYBRID = "hybrid"
    DIRECT = "direct"  # Baseline LLM puro: sem grafo, sem retrieval.
    TREE = "tree"  # Chatbot tradicional: árvore de decisão, sem LLM.


class GoldenQuestion(BaseModel):
    """Pergunta sintética gerada para o benchmark com ground truth."""

    question: str
    question_type: QuestionType = QuestionType.UNMAPPED
    ground_truth: str
    source_document: str = ""


class QueryInteractionSource(StrEnum):
    """Origem do retorno da consulta."""

    LIGHTRAG_ENGINE = "lightrag_engine"
    SEMANTIC_CACHE = "semantic_cache"
    BASELINE_ENGINE = "baseline_engine"
    TREE_ENGINE = "tree_engine"


class RagExecutionStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


class QueryExecutionRecord(BaseModel):
    """Registro individual de execução de uma pergunta no RAG."""

    index: int = 0
    query: str
    response: str | None = None
    mode: SearchMode = SearchMode.HYBRID
    top_k: int = 5
    model: str = ""
    source: QueryInteractionSource = QueryInteractionSource.LIGHTRAG_ENGINE
    similarity_score: float | None = None
    total_latency_seconds: float = 0.0
    rag_retrieval_latency_seconds: float | None = None
    ttft_seconds: float | None = None
    status: RagExecutionStatus = RagExecutionStatus.SUCCESS
    error_message: str | None = None
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
    datetime_str: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class RagasMetrics(BaseModel):
    """Scores consolidados das métricas RAGAS."""

    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_recall: float | None = None
    context_precision: float | None = None


class EvaluatedSample(BaseModel):
    """Amostra unificada: Pergunta + Resposta + Contexto + Ground Truth + Métricas + Latência."""

    question: str
    answer: str
    context: str
    ground_truth: str
    question_type: str = "UNMAPPED"
    metrics: RagasMetrics = Field(default_factory=RagasMetrics)
    total_latency_seconds: float | None = None
    ttft_seconds: float | None = None
    search_mode: str | None = None


class IndexedDocument(BaseModel):
    """Registro de um POP já inserido no grafo (anti-duplicata por hash)."""

    filename: str
    sha256: str
    num_bytes: int = 0
    indexed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class IndexManifest(BaseModel):
    """Manifesto de indexação: quais hashes de conteúdo já estão no grafo."""

    version: int = 1
    documents: list[IndexedDocument] = []

    def known_hashes(self) -> set[str]:
        """Hashes já indexados (para skip incremental)."""
        return {doc.sha256 for doc in self.documents}

    def known_filenames(self) -> set[str]:
        """Nomes de arquivo já vistos (para detectar conteúdo alterado)."""
        return {doc.filename for doc in self.documents}

    def upsert(self, entry: IndexedDocument) -> None:
        """Insere ou atualiza o registro de um arquivo pelo nome."""
        for i, doc in enumerate(self.documents):
            if doc.filename == entry.filename:
                self.documents[i] = entry
                return
        self.documents.append(entry)


class ReconcileReport(BaseModel):
    """Resultado da reconciliação do manifesto com o grafo LightRAG existente."""

    reconciled: list[str] = Field(default_factory=list)
    altered: list[str] = Field(default_factory=list)
    missing_on_disk: list[str] = Field(default_factory=list)
    ignored_non_processed: int = 0
    manifest_written: bool = False


class RunManifest(BaseModel):
    """Manifesto com metadados para reprodutibilidade científica do experimento."""

    run_id: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    git_commit: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    total_queries: int = 0
    completed_queries: int = 0
    failed_queries: int = 0
    cache_hit_rate: float = 0.0
    mean_latency_seconds: float = 0.0
    mean_ttft_seconds: float = 0.0
