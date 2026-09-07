import asyncio
import json
import re
from pathlib import Path
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

# ---------------------------------------------------------
# Configuração de Diretórios e Constantes
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).parent.name == "src" else Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "entradas" / "pops"
OUTPUT_DIR = BASE_DIR / "entradas" / "perguntas"
OUTPUT_FILE = OUTPUT_DIR / "golden_dataset.json"

MODEL_NAME = "qwen2.5:3b"
QUESTIONS_PER_DOC = 10

client = AsyncOpenAI(base_url="http://localhost:11434/v1/", api_key="ollama_local")

# ---------------------------------------------------------
# Prompt com Foco em Alta Complexidade & Raciocínio Adversarial
# ---------------------------------------------------------
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

async def generate_questions_for_doc(file_path: Path) -> list[dict]:
    doc_text = file_path.read_text(encoding="utf-8")
    doc_name = file_path.name

    prompt = USER_PROMPT_TEMPLATE.format(
        num_questions=QUESTIONS_PER_DOC,
        doc_name=doc_name,
        doc_text=doc_text
    )

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content.strip()

        # Sanitização robusta
        if content.startswith("```"):
            content = re.sub(r"^```(?:json|JSON)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        content = content.strip()

        try:
            parsed_data = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                parsed_data = json.loads(match.group(0))
            else:
                print(f"  [ERRO] Falha ao parsear JSON para {doc_name}")
                return []

        questions_list = parsed_data.get("questions", [])
        if not isinstance(questions_list, list):
            return []

        for q in questions_list:
            if isinstance(q, dict):
                q["source_document"] = doc_name

        print(f"  [OK] Geradas {len(questions_list)} perguntas complexas para: {doc_name}")
        return questions_list

    except Exception as e:
        print(f"  [ERRO] Falha na execução para {doc_name}: {str(e)}")
        return []

async def main():
    print("==================================================")
    print("[1/3] Iniciando Geração de Dataset Avançado (Golden Dataset)...")
    print("==================================================")

    if not INPUT_DIR.exists():
        print(f"❌ Diretório não encontrado: {INPUT_DIR}")
        return

    arquivos_txt = list(INPUT_DIR.glob("*.txt"))
    if not arquivos_txt:
        print(f"❌ Nenhum arquivo .txt em {INPUT_DIR}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[2/3] Gerando {QUESTIONS_PER_DOC} perguntas por doc via {MODEL_NAME} em {len(arquivos_txt)} arquivos...")
    
    tasks = [generate_questions_for_doc(doc) for doc in arquivos_txt]
    results = await asyncio.gather(*tasks)

    # Filtering defensivo para impedir NoneType no flatten
    golden_dataset = [item for sublist in results if sublist for item in sublist]

    print("==================================================")
    print("[3/3] Exportando Dataset Gerado...")
    print("==================================================")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(golden_dataset, f, ensure_ascii=False, indent=2)

    print(f"✅ Golden Dataset atualizado com sucesso!")
    print(f"📌 Total de Perguntas Geradas: {len(golden_dataset)}")
    print(f"📁 Localização: {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())