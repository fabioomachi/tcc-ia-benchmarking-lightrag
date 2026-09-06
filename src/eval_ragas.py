import json
import pandas as pd
from pathlib import Path
from datasets import Dataset

# Métricas do RAGAS sem exigência obrigatória de 'ground_truth'
from ragas import evaluate
from ragas.metrics import (
    faithfulness,         # Fidelidade à base (mitigação de alucinação)
    answer_relevancy,     # Relevância da resposta em relação à pergunta
    context_utilization   # Substitui context_precision para datasets sem ground_truth
)

# Wrappers de Chat e Embedding via LangChain
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings

# 1. Configuração de Caminhos
BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).parent.name == "src" else Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "logs" / "benchmark_execution.log"
RESULT_DIR = BASE_DIR / "result"
RESULT_DIR.mkdir(exist_ok=True)

def load_data_from_logs():
    """Extrai as queries, respostas e contextos capturados nos logs estruturados."""
    if not LOG_FILE.exists():
        raise FileNotFoundError(f"Arquivo de log não encontrado em: {LOG_FILE}")

    questions = []
    answers = []
    contexts = []

    prompts_cache = {}
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): 
                continue
            try:
                event = json.loads(line)
                event_type = event.get("event_type")
                data = event.get("data", {})

                # Mapeia o prompt/contexto recuperado do LightRAG
                if event_type == "llm_input_prompt":
                    prompts_cache[data.get("raw_prompt_payload", "")] = data.get("system_prompt", "")

                # Captura execuções diretas do LightRAG Engine
                elif event_type == "interaction_record" and data.get("source") == "lightrag_engine":
                    query = data.get("user_query")
                    response = data.get("final_response")
                    
                    context_text = prompts_cache.get(query, "Sem contexto explícito capturado no log.")

                    questions.append(query)
                    answers.append(response)
                    # O RAGAS requer contextos no formato List[str]
                    contexts.append([context_text])

            except json.JSONDecodeError:
                continue

    return {
        "question": questions,
        "answer": answers,
        "contexts": contexts
    }

def run_ragas_evaluation():
    print("🔄 Carregando dados de execuções dos logs...")
    raw_data = load_data_from_logs()

    if not raw_data["question"]:
        print("⚠️ Nenhum registro da 'lightrag_engine' encontrado nos logs para avaliação.")
        return

    dataset = Dataset.from_dict(raw_data)
    print(f"✅ Total de amostras prontas para avaliação: {len(dataset)}")

    # 2. Instanciação dos Modelos Locais para Atuar como Avaliadores (LLM Judge)
    print("🤖 Configurando ChatOllama (qwen2.5:3b) e Embeddings (all-minilm)...")
    evaluator_llm = ChatOllama(model="qwen2.5:3b", base_url="http://localhost:11434")
    evaluator_embeddings = OllamaEmbeddings(model="all-minilm", base_url="http://localhost:11434")

    # 3. Execução da Avaliação
    print("📊 Calculando métricas do RAGAS (Faithfulness, Relevancy, Context Utilization)...")
    results = evaluate(
        dataset=dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_utilization
        ],
        llm=evaluator_llm,
        embeddings=evaluator_embeddings
    )

    print("\n=== RESULTADOS DO RAGAS ===")
    print(results)

    # 4. Exportação dos Resultados
    df_results = results.to_pandas()
    output_csv = RESULT_DIR / "ragas_evaluation_results.csv"
    df_results.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"\n✅ Relatório do RAGAS exportado com sucesso para: {output_csv}")

if __name__ == "__main__":
    run_ragas_evaluation()