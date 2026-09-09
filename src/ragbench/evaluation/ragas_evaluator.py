import json
import logging
import re
from pathlib import Path

import pandas as pd
from datasets import Dataset
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from ragas import evaluate
from ragas.metrics import (
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
    """Avaliador LLM-as-a-Judge utilizando RAGAS com modelos locais servidos via Ollama."""

    def __init__(self, settings: BenchmarkSettings | None = None):
        self.settings = settings or global_settings

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
            if rec.status != "success" or not rec.response:
                continue

            q_norm = self._normalize_text(rec.query)
            golden_item = golden_map.get(q_norm, {})

            gt = golden_item.get("ground_truth", "N/A")
            q_type = golden_item.get("question_type", "UNMAPPED")

            questions.append(rec.query)
            answers.append(rec.response)
            contexts.append([default_context])
            ground_truths.append(gt)
            question_types.append(q_type)
            latencies.append(rec.total_latency_seconds)
            ttfts.append(rec.ttft_seconds)

        if not questions:
            raise EvaluationError("Nenhuma consulta válida encontrada para submeter ao RAGAS.")

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

        ollama_http_url = self.settings.ollama.base_url.rstrip("/").replace("/v1", "")

        evaluator_llm = ChatOllama(
            model=self.settings.ragas.judge_model,
            base_url=ollama_http_url,
            temperature=0.0,
            num_ctx=self.settings.ragas.num_ctx,
            timeout=self.settings.ragas.timeout,
        )

        evaluator_embeddings = OllamaEmbeddings(
            model=self.settings.ragas.embed_model,
            base_url=ollama_http_url,
        )

        logger.info(
            f"Iniciando bateria RAGAS em {len(dataset)} amostras com modelo {self.settings.ragas.judge_model}..."
        )

        try:
            results = evaluate(
                dataset=dataset,
                metrics=[
                    faithfulness,
                    answer_relevancy,
                    context_recall,
                    context_precision,
                ],
                llm=evaluator_llm,
                embeddings=evaluator_embeddings,
                raise_exceptions=False,
                run_config=RunConfig(
                    max_workers=self.settings.ragas.max_workers,
                    timeout=self.settings.ragas.timeout,
                ),
            )
            df_ragas = results.to_pandas()
            return df_ragas
        except Exception as e:
            logger.error(f"Falha na orquestração do RAGAS: {e}")
            raise EvaluationError(f"Erro no pipeline RAGAS: {e}") from e
