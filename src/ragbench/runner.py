import asyncio
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from ragbench.config import BenchmarkSettings
from ragbench.config import settings as global_settings
from ragbench.core.models import (
    QueryExecutionRecord,
    QueryInteractionSource,
    RagExecutionStatus,
    SearchMode,
)
from ragbench.engines.lightrag_engine import LightRAGEngine
from ragbench.infrastructure.semantic_cache import SemanticCache
from ragbench.infrastructure.storage import SQLiteExecutionStorage

logger = logging.getLogger("ragbench.runner")


class BenchmarkRunner:
    """Orquestrador de execução em lote com concorrência adaptativa e tolerância a falhas."""

    def __init__(
        self,
        engine: LightRAGEngine,
        storage: SQLiteExecutionStorage,
        cache: SemanticCache | None = None,
        settings: BenchmarkSettings | None = None,
    ):
        self.engine = engine
        self.storage = storage
        self.settings = settings or global_settings
        self.cache = cache or SemanticCache(threshold=self.settings.cache_threshold)

    @staticmethod
    def load_queries_from_path(target_path: Path) -> list[str]:
        """Extrai perguntas de arquivos .txt ou .json (inclusive pastas)."""
        if not target_path.exists():
            raise FileNotFoundError(f"Caminho não encontrado: {target_path}")

        files = []
        if target_path.is_file():
            files = [target_path]
        else:
            files = list(target_path.glob("*.txt")) + list(target_path.glob("*.json"))

        queries: list[str] = []
        for file in files:
            if file.suffix == ".json":
                try:
                    with open(file, encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            for item in data:
                                q = item.get("question") if isinstance(item, dict) else str(item)
                                if q and q.strip():
                                    queries.append(q.strip())
                        elif isinstance(data, dict):
                            q = data.get("question")
                            if q and q.strip():
                                queries.append(q.strip())
                except Exception as e:
                    logger.error(f"Erro ao parsear arquivo JSON {file}: {e}")
            else:
                with open(file, encoding="utf-8") as f:
                    for line in f:
                        clean_line = line.strip()
                        if clean_line:
                            queries.append(clean_line)

        return queries

    async def execute_batch(
        self,
        queries: list[str],
        mode: SearchMode = SearchMode.HYBRID,
        top_k: int = 5,
        concurrency: int = 10,
        resume: bool = True,
        on_progress: Callable[[int, int, QueryExecutionRecord], None] | None = None,
    ) -> list[QueryExecutionRecord]:
        """Executa lote de perguntas com controle de concorrência e checkpointing."""
        completed_indices = self.storage.get_completed_indices() if resume else set()
        total_queries = len(queries)

        if completed_indices:
            logger.info(
                f"Modo Resume ativado: {len(completed_indices)}/{total_queries} perguntas já concluídas anteriormente."
            )

        semaphore = asyncio.Semaphore(concurrency)
        results: list[QueryExecutionRecord] = []

        async def worker(idx: int, query_text: str) -> QueryExecutionRecord:
            if idx in completed_indices:
                # Já executado e salvo anteriormente
                return None  # type: ignore

            async with semaphore:
                start_time = time.perf_counter()
                record = QueryExecutionRecord(
                    index=idx,
                    query=query_text,
                    mode=mode,
                    top_k=top_k,
                    model=self.settings.lightrag.llm_model,
                )

                # 1. Checagem de Cache Semântico
                try:
                    query_embs = await self.engine.ollama_client.get_embeddings(
                        model=self.settings.lightrag.embed_model,
                        texts=[query_text],
                    )
                    if len(query_embs) > 0:
                        cached_resp, similarity = self.cache.get(query_embs[0])
                        if cached_resp:
                            record.response = cached_resp
                            record.source = QueryInteractionSource.SEMANTIC_CACHE
                            record.similarity_score = round(similarity, 4)
                            record.total_latency_seconds = round(
                                time.perf_counter() - start_time, 4
                            )
                            record.status = RagExecutionStatus.SUCCESS
                            self.storage.save_record(record)
                            return record
                except Exception as e:
                    logger.debug(f"Bypass de cache devido a erro transitório: {e}")

                # 2. Execução no Motor RAG
                rag_start = time.perf_counter()
                try:
                    response = await self.engine.aquery(
                        query=query_text,
                        mode=mode,
                        top_k=top_k,
                        stream=False,
                    )
                    rag_latency = time.perf_counter() - rag_start
                    total_latency = time.perf_counter() - start_time

                    record.response = str(response)
                    record.source = QueryInteractionSource.LIGHTRAG_ENGINE
                    record.rag_retrieval_latency_seconds = round(rag_latency, 4)
                    record.total_latency_seconds = round(total_latency, 4)
                    record.status = RagExecutionStatus.SUCCESS

                    if len(query_embs) > 0:
                        self.cache.add(query_embs[0], str(response))

                except Exception as e:
                    total_latency = time.perf_counter() - start_time
                    record.status = RagExecutionStatus.ERROR
                    record.error_message = f"{type(e).__name__}: {str(e)}"
                    record.total_latency_seconds = round(total_latency, 4)
                    logger.error(f"Erro na query #{idx}: {record.error_message}")

                self.storage.save_record(record)
                return record

        tasks = [worker(i, q) for i, q in enumerate(queries)]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task_id = progress.add_task("Executando benchmark...", total=total_queries)
            progress.update(task_id, completed=len(completed_indices))

            for coro in asyncio.as_completed(tasks):
                res = await coro
                if res is not None:
                    results.append(res)
                    progress.update(task_id, advance=1)
                    if on_progress:
                        on_progress(len(results), total_queries, res)

        return self.storage.load_all_records()
