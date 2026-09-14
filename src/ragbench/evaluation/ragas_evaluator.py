import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from datasets import Dataset
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI
from ragas import evaluate
from ragas.metrics import (
    AnswerRelevancy,
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)
from ragas.run_config import RunConfig

from ragbench.config import BenchmarkSettings, get_settings
from ragbench.core.exceptions import EvaluationError, OllamaConnectionError
from ragbench.core.models import QueryExecutionRecord
from ragbench.infrastructure.logging import get_logger

logger = get_logger("ragbench.evaluation.ragas")

# Colunas de score do RAGAS — único escopo válido para o alerta de NaN.
_SCORE_COLUMNS = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]


class GeminiRestEmbeddings(Embeddings):
    """Embeddings Gemini via REST `:embedContent` (síncrono, padrão langchain).

    O RAGAS consome apenas `embed_query`/`embed_documents` síncronos, e o
    endpoint OpenAI-compatível do Gemini retorna 501 para `/embeddings` —
    por isso este wrapper usa o REST nativo, mesmo contrato do
    `ResilientOllamaClient.get_embeddings`. Falhas após retries levantam
    `OllamaConnectionError` (vira retry no RunConfig e, se esgotado, NaN).
    """

    def __init__(
        self,
        api_key: str,
        api_base_url: str,
        model: str,
        dim: int = 768,
        timeout: float = 10.0,
        max_attempts: int = 3,
        retry_delay: float = 2.0,
    ):
        self.api_key = api_key
        self.url = f"{api_base_url.rstrip('/')}/{model}:embedContent"
        self.dim = dim
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay

    def _embed_one(self, client: httpx.Client, text: str) -> list[float]:
        payload = {"content": {"parts": [{"text": text}]}, "outputDimensionality": self.dim}
        headers = {"x-goog-api-key": self.api_key}
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                resp = client.post(self.url, json=payload, headers=headers)
                if resp.status_code == 429:
                    time.sleep(self.retry_delay * attempt)
                    continue
                resp.raise_for_status()
                return resp.json().get("embedding", {}).get("values", [0.0] * self.dim)
            except Exception as e:
                last_error = e
                if attempt < self.max_attempts:
                    time.sleep(self.retry_delay)
        raise OllamaConnectionError(f"Falha no embedding Gemini REST: {last_error}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        with httpx.Client(timeout=self.timeout) as client:
            return [self._embed_one(client, t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def select_relevancy_metric(judge_model: str) -> Any:
    """Escolhe a métrica answer_relevancy conforme o transporte (puro: sem I/O).

    Gemini rejeita candidateCount > 1 com 400, e o answer_relevancy padrão usa
    strictness=3 (n=3 gerações) — por isso força candidato único no Gemini.
    """
    if (judge_model or "").startswith("gemini-"):
        return AnswerRelevancy(strictness=1)
    return answer_relevancy


class RagasEvaluator:
    """Avaliador LLM-as-a-Judge via RAGAS sobre transporte Gemini unificado.

    O juiz usa o MESMO endpoint Gemini do index/chat (OpenAI-compatível),
    diferenciando apenas o modelo (`RAGAS__JUDGE_MODEL`, ex: `gemini-3.8-flash`).
    Modelos sem prefixo `gemini-` mantêm fallback Ollama local.
    """

    def __init__(
        self,
        settings: BenchmarkSettings | None = None,
        judge_llm_factory: Callable[[], Any] | None = None,
        embeddings_factory: Callable[[], Any] | None = None,
        evaluate_fn: Callable[..., Any] | None = None,
    ):
        self.settings = settings or get_settings()
        self._judge_llm_factory = judge_llm_factory or self._build_judge_llm
        self._embeddings_factory = embeddings_factory or self._build_embeddings
        self._evaluate_fn = evaluate_fn or evaluate

    @staticmethod
    def _is_gemini_model(model: str) -> bool:
        return (model or "").startswith("gemini-")

    def _build_judge_llm(self):
        """Juiz RAGAS: Gemini via ChatOpenAI ou fallback Ollama local."""
        model = self.settings.ragas.judge_model
        if self._is_gemini_model(model):
            return ChatOpenAI(
                model=model,
                openai_api_base=self.settings.ollama.base_url,
                openai_api_key=self.settings.ollama.api_key,
                temperature=0.0,
                timeout=self.settings.ragas.timeout,
                max_retries=self.settings.ragas.judge_max_retries,
            )
        ollama_http_url = self.settings.chat.base_url.rstrip("/").replace("/v1", "")
        return ChatOllama(
            model=model,
            base_url=ollama_http_url,
            temperature=0.0,
            num_ctx=self.settings.ragas.num_ctx,
            timeout=self.settings.ragas.timeout,
        )

    def _build_embeddings(self):
        """Embeddings do RAGAS: Gemini via REST ou fallback Ollama.

        O endpoint OpenAI-compatível do Gemini não implementa `/embeddings`
        (501 UNIMPLEMENTED), então usa o REST `:embedContent` — o mesmo caminho
        testado do `ResilientOllamaClient.get_embeddings`.
        """
        model = self.settings.ragas.embed_model
        if self._is_gemini_model(model):
            return GeminiRestEmbeddings(
                api_key=self.settings.ollama.api_key,
                api_base_url=self.settings.ollama.embedding_api_base_url,
                model=model,
                dim=self.settings.ollama.embedding_default_dim,
                timeout=self.settings.ollama.embedding_timeout,
                max_attempts=self.settings.ollama.embedding_max_attempts,
                retry_delay=self.settings.ollama.embedding_retry_delay,
            )
        ollama_http_url = self.settings.chat.base_url.rstrip("/").replace("/v1", "")
        return OllamaEmbeddings(
            model=model,
            base_url=ollama_http_url,
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        if not text:
            return ""
        text = text.lower().strip()
        return re.sub(r"\s+", " ", text)

    def load_golden_map(self, golden_path: Path) -> dict[str, dict]:
        if not golden_path.exists():
            logger.warning(f"Golden dataset não encontrado em {golden_path}")
            return {}
        with open(golden_path, encoding="utf-8") as f:
            try:
                data = json.load(f)
                return {self._normalize_text(item["question"]): item for item in data}
            except json.JSONDecodeError as e:
                logger.error(f"Erro ao parsear golden dataset: {e}")
                return {}

    def prepare_dataset(
        self,
        records: list[QueryExecutionRecord],
        golden_path: Path,
        default_context: str = "Regras operacionais padrão de compliance bancário extraídas do grafo.",
    ) -> Dataset:
        golden_map = self.load_golden_map(golden_path)

        questions, answers, contexts, ground_truths, question_types, latencies, ttfts = (
            [],
            [],
            [],
            [],
            [],
            [],
            [],
        )

        for rec in records:
            # 1. Converte o status para string minúscula para ignorar diferenças de maiúsculas/minúsculas
            status_str = str(rec.status).lower() if rec.status is not None else ""

            # 2. Aceita status válidos de sucesso e valida a existência da resposta
            if status_str not in ("success", "ok", "completed") or not rec.response:
                logger.warning(
                    f"⚠️ Registro ignorado [ID: {getattr(rec, 'query_id', 'N/A')}]: "
                    f"status='{rec.status}', tem_resposta={bool(rec.response)}"
                )
                continue

            q_norm = self._normalize_text(rec.query)
            golden_item = golden_map.get(q_norm, {})

            gt = golden_item.get("ground_truth", "N/A")
            q_type = golden_item.get("question_type", "UNMAPPED")
            source_doc = golden_item.get("source_document", "")

            context_text = default_context
            if source_doc:
                doc_path = self.settings.pops_dir / source_doc
                if doc_path.exists():
                    context_text = doc_path.read_text(encoding="utf-8")

            questions.append(rec.query)
            answers.append(rec.response)
            contexts.append([context_text])
            ground_truths.append(gt)
            question_types.append(q_type)
            latencies.append(rec.total_latency_seconds)
            ttfts.append(rec.ttft_seconds)

        if not questions:
            raise EvaluationError(
                f"Nenhuma consulta válida encontrada entre os {len(records)} registros recarregados do checkpoint."
            )

        return Dataset.from_dict(
            {
                "question": questions,
                "answer": answers,
                "contexts": contexts,
                "ground_truth": ground_truths,
                "question_type": question_types,
                "latencia_total_s": latencies,
                "ttft_s": ttfts,
            }
        )

    def run_evaluation(
        self,
        records: list[QueryExecutionRecord],
        golden_path: Path | None = None,
    ) -> pd.DataFrame:
        """Executa avaliação do RAGAS e retorna DataFrame unificado com métricas e latência."""
        target_golden = golden_path or (self.settings.questions_dir / "golden_dataset.json")
        dataset = self.prepare_dataset(records, target_golden)

        evaluator_llm = self._judge_llm_factory()
        evaluator_embeddings = self._embeddings_factory()

        logger.info(
            f"Iniciando bateria RAGAS em {len(dataset)} amostras com modelo {self.settings.ragas.judge_model}..."
        )

        try:
            relevancy_metric = select_relevancy_metric(self.settings.ragas.judge_model)
            results = self._evaluate_fn(
                dataset=dataset,
                metrics=[
                    faithfulness,
                    relevancy_metric,
                    context_recall,
                    context_precision,
                ],
                llm=evaluator_llm,
                embeddings=evaluator_embeddings,
                raise_exceptions=False,
                run_config=RunConfig(
                    max_workers=self.settings.ragas.max_workers,
                    timeout=self.settings.ragas.timeout,
                    # 503 UNAVAILABLE / 429 são transitórios (pico de demanda no
                    # Gemini). Backoff exponencial longo atravessa o pico em vez
                    # de falhar o Job. Com raise_exceptions=False, jobs que
                    # esgotarem os retries viram NaN em vez de abortar o eval.
                    max_retries=self.settings.ragas.run_max_retries,
                    max_wait=self.settings.ragas.run_max_wait,
                    log_tenacity=True,
                ),
            )
            df_ragas = results.to_pandas()
            # Conta NaN SÓ nas colunas de métrica: colunas de telemetria
            # (ex: ttft_s) podem ser nulas no checkpoint sem indicar falha.
            score_cols = [c for c in _SCORE_COLUMNS if c in df_ragas.columns]
            scope = df_ragas[score_cols] if score_cols else df_ragas
            n_nan = int(scope.isna().any(axis=1).sum()) if not scope.empty else 0
            if n_nan:
                logger.warning(
                    f"{n_nan}/{len(df_ragas)} linhas com NaN nas métricas (jobs que "
                    "esgotaram retries após 4xx/5xx do Gemini — ex: 429/503 em "
                    "pico de demanda. Reexecute o eval, picos são temporários)."
                )
            return df_ragas
        except Exception as e:
            logger.error(f"Falha na orquestração do RAGAS: {e}")
            raise EvaluationError(f"Erro no pipeline RAGAS: {e}") from e
