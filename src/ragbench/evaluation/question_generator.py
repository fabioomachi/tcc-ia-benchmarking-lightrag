import asyncio
import json
import logging
import re
from itertools import chain
from pathlib import Path

from ragbench.config import BenchmarkSettings, get_settings
from ragbench.core.models import GoldenQuestion, QuestionType
from ragbench.infrastructure.ollama_client import ResilientOllamaClient

logger = logging.getLogger("ragbench.evaluation.dataset_gen")

SYSTEM_PROMPT = """Você é um Lead QA Automation Engineer & Banking Auditor especializado em testes adversariais para sistemas RAG.
Sua missão é gerar um Golden Dataset com perguntas complexas, não-triviais e situacionais a partir de Procedimentos Operacionais Padrão (POPs) bancários.

Sua meta é TESTAR OS LIMITES de um RAG. Evite perguntas com respostas diretas/literais ("O que é X?").
Priorize perguntas que exijam:
1. Análise de cenários hipotéticos de borda (edge cases).
2. Validação de pré-requisitos múltiplos para tomada de decisão.
3. Raciocínio sobre restrições de tempo, prazos e exceções de compliance.
4. Identificação do que É PROIBIDO ou do que OCORRE EM CASO DE FALHA.
"""

USER_PROMPT_TEMPLATE = """Analise o Procedimento Operacional Padrão abaixo e gere exatamente {num_questions} perguntas de ALTA COMPLEXIDADE com suas respectivas respostas de referência (ground_truth).

Documento: {doc_name}
---
{doc_text}
---

Distribua as {num_questions} perguntas tentando cobrir estas categorias:
- "EDGE_CASE": Situação limite ou conflito com exceção.
- "REGULATORY_TIMELINE": Impacto de descumprimento de prazos ou gatilhos temporais.
- "CONDITIONAL_WORKFLOW": Exigência de múltiplas condições simultâneas para uma ação.
- "ROLE_RESTRICTION": Limites de alçada, atores proibidos e responsabilidades.

Responda ESTRITAMENTE no formato JSON com o seguinte esquema:
{{
  "questions": [
    {{
      "question": "Pergunta elaborada baseada em um cenário hipotético ou analítico complexo",
      "question_type": "EDGE_CASE | REGULATORY_TIMELINE | CONDITIONAL_WORKFLOW | ROLE_RESTRICTION",
      "ground_truth": "Resposta analítica precisa e completa fundamentada exclusivamente no texto."
    }}
  ]
}}
"""


def build_user_prompt(doc_name: str, doc_text: str, num_questions: int) -> str:
    """Monta o prompt do usuário para geração (puro: sem I/O, testável)."""
    return USER_PROMPT_TEMPLATE.format(
        num_questions=num_questions,
        doc_name=doc_name,
        doc_text=doc_text,
    )


def strip_fences(content: str) -> str:
    """Remove cercas de markdown (```json ... ```) da resposta do LLM."""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json|JSON)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_questions(content: str, doc_name: str) -> list[GoldenQuestion]:
    """Converte a resposta bruta do LLM em perguntas tipadas (puro: sem I/O).

    Retorna [] quando o JSON é irrecuperável; tipos desconhecidos viram UNMAPPED.
    """
    text = strip_fences(content)

    try:
        parsed_data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            logger.error(f"Falha ao decodificar JSON para {doc_name}")
            return []
        try:
            parsed_data = json.loads(match.group(0))
        except json.JSONDecodeError:
            logger.error(f"Falha ao decodificar JSON (fallback) para {doc_name}")
            return []

    raw_questions = parsed_data.get("questions", [])
    questions: list[GoldenQuestion] = []
    for item in raw_questions:
        if isinstance(item, dict):
            q_type = item.get("question_type", "UNMAPPED")
            try:
                valid_type = QuestionType(q_type)
            except ValueError:
                valid_type = QuestionType.UNMAPPED

            questions.append(
                GoldenQuestion(
                    question=item.get("question", "").strip(),
                    question_type=valid_type,
                    ground_truth=item.get("ground_truth", "").strip(),
                    source_document=doc_name,
                )
            )
    return questions


class GoldenDatasetGenerator:
    """Gerador sintético de datasets de perguntas adversariais tipadas a partir de POPs."""

    def __init__(
        self,
        settings: BenchmarkSettings | None = None,
        ollama_client: ResilientOllamaClient | None = None,
    ):
        self.settings = settings or get_settings()
        self.ollama_client = ollama_client or ResilientOllamaClient(self.settings.ollama)

    async def generate_for_doc(
        self, file_path: Path, questions_per_doc: int = 2
    ) -> list[GoldenQuestion]:
        """Gera perguntas para um único documento de POP."""
        doc_text = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
        doc_name = file_path.name

        prompt = build_user_prompt(doc_name, doc_text, questions_per_doc)

        try:
            content = await self.ollama_client.generate_completion(
                model=self.settings.lightrag.llm_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            questions = parse_questions(content, doc_name)
            logger.info(f"Geradas {len(questions)} perguntas com sucesso para {doc_name}")
            return questions

        except Exception as e:
            logger.error(f"Erro ao gerar perguntas para {doc_name}: {e}")
            return []

    async def generate_dataset(
        self,
        input_dir: Path | None = None,
        output_file: Path | None = None,
        questions_per_doc: int = 2,
        concurrency: int | None = None,
    ) -> list[GoldenQuestion]:
        """Gera dataset para todos os arquivos de texto encontrados na pasta."""
        in_dir = input_dir or self.settings.pops_dir
        out_file = output_file or (self.settings.questions_dir / "golden_dataset.json")
        out_file.parent.mkdir(parents=True, exist_ok=True)

        txt_files = list(chain(in_dir.glob("*.txt"), in_dir.glob("*.md")))
        if not txt_files:
            logger.warning(f"Nenhum arquivo .txt encontrado em {in_dir}")
            return []

        limit = max(1, concurrency or self.settings.concurrency_limit)
        semaphore = asyncio.Semaphore(limit)

        async def _bounded(doc: Path) -> list[GoldenQuestion]:
            async with semaphore:
                return await self.generate_for_doc(doc, questions_per_doc)

        tasks = [_bounded(f) for f in txt_files]
        results = await asyncio.gather(*tasks)

        dataset = [q for sublist in results for q in sublist if q.question]

        payload = json.dumps([q.model_dump() for q in dataset], ensure_ascii=False, indent=2)
        await asyncio.to_thread(out_file.write_text, payload, encoding="utf-8")

        logger.info(f"Golden dataset salvo com sucesso em {out_file} ({len(dataset)} perguntas)")
        return dataset
