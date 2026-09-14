import json
import logging
import re
from pathlib import Path

import pandas as pd
from datasets import Dataset
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import evaluate
from ragas.metrics import (
    AnswerRelevancy,
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)
from ragas.run_config import RunConfig

from ragbench.config import BenchmarkSettings
from ragbench.config import settings as global_settings
from ragbench.core.exceptions import EvaluationError
from ragbench.core.models import QueryExecutionRecord

logger = logging.getLogger("ragbench.evaluation.ragas")


class RagasEvaluator:
    """Avaliador LLM-as-a-Judge via RAGAS sobre transporte Gemini unificado.

    O juiz usa o MESMO endpoint Gemini do index/chat (OpenAI-compatível),
    diferenciando apenas o modelo (`RAGAS__JUDGE_MODEL`, ex: `gemini-3.8-flash`).
    Modelos sem prefixo `gemini-` mantêm fallback Ollama local.
    """

    def __init__(self, settings: BenchmarkSettings | None = None):
        self.settings = settings or global_settings

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
        """Embeddings do RAGAS: Gemini via OpenAI-compat ou fallback Ollama."""
        model = self.settings.ragas.embed_model
        if self._is_gemini_model(model):
            return OpenAIEmbeddings(
                model=model,
                openai_api_base=self.settings.ollama.base_url,
                openai_api_key=self.settings.ollama.api_key,
                timeout=self.settings.ollama.embedding_timeout,
                max_retries=self.settings.ollama.max_retries,
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

        evaluator_llm = self._build_judge_llm()
        evaluator_embeddings = self._build_embeddings()

        logger.info(
            f"Iniciando bateria RAGAS em {len(dataset)} amostras com modelo {self.settings.ragas.judge_model}..."
        )

        try:
            # Gemini (ex: gemini-3.8-flash) rejeita candidateCount > 1 com 400
            # "Multiple candidates is not enabled for this model". O
            # answer_relevancy padrão usa strictness=3 (n=3 gerações), então
            # força candidato único no transporte Gemini. Demais métricas já
            # usam reproducibility=1 por padrão.
            relevancy_metric = (
                AnswerRelevancy(strictness=1)
                if self._is_gemini_model(self.settings.ragas.judge_model)
                else answer_relevancy
            )
            results = evaluate(
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
            n_nan = int(df_ragas.isna().any(axis=1).sum()) if not df_ragas.empty else 0
            if n_nan:
                logger.warning(
                    f"{n_nan}/{len(df_ragas)} linhas com NaN (jobs que esgotaram "
                    "retries em 429/503). Reexecute o eval — picos são temporários."
                )
            return df_ragas
        except Exception as e:
            logger.error(f"Falha na orquestração do RAGAS: {e}")
            raise EvaluationError(f"Erro no pipeline RAGAS: {e}") from e
