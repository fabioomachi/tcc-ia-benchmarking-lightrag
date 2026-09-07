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
RESULT_DIR = BASE_DIR / "resultados"
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

    #print("🤖 Configurando LLM Judge (Recomendado: llama3.1:8b ou superior) e Embeddings...")
    #evaluator_llm = ChatOllama(model="llama3.1:8b", base_url="http://localhost:11434", temperature=0.0)
    #evaluator_embeddings = OllamaEmbeddings(model="all-minilm", base_url="http://localhost:11434")

    # 3. Resiliência e Paralelismo na Orquestração do RAGAS
    print("📊 Calculando métricas... (Isso pode demorar dependendo da GPU)")
    try:
        results = evaluate(
            dataset=dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_utilization
            ],
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
            raise_exceptions=False # Impede que o script quebre inteiro se o LLM falhar em uma query
        )
    except Exception as e:
        print(f"❌ Falha crítica na orquestração do RAGAS: {e}")
        return

    # 4. Merge de Rastreabilidade (Qualidade + Performance)
    df_ragas = results.to_pandas()
    
    # Tentativa de fundir com as métricas de latência já parseadas pelo analisa_logs.py
    analise_detalhada_path = RESULT_DIR / "benchmark_analise_detalhada.csv"
    if analise_detalhada_path.exists():
        df_performance = pd.read_csv(analise_detalhada_path)
        # Faz o join pela pergunta para ter os scores e a latência na mesma linha
        df_final = pd.merge(df_ragas, df_performance, left_on="question", right_on="pergunta", how="left")
        df_final.drop(columns=["pergunta"], inplace=True) # Remove duplicidade
    else:
        df_final = df_ragas

    # Geração do df_final e salvamento do CSV)
    output_csv = RESULT_DIR / "ragas_evaluation_results.csv"
    df_final.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"\n✅ Relatório integrado exportado com sucesso para: {output_csv}")

    # Geração do Relatório Sintético
    report_md = RESULT_DIR / "resumo_qualidade_ragas.md"
    generate_synthetic_report(df_final, report_md)
    print(f"✅ Relatório sintético gerado em: {report_md}")    

def generate_synthetic_report(df: pd.DataFrame, output_path: Path):
    """Gera um relatório executivo em Markdown com base nas métricas avaliadas."""
    
    # Filtra as métricas geradas pelo RAGAS
    metric_cols = [col for col in ['faithfulness', 'answer_relevancy', 'context_utilization'] if col in df.columns]
    
    if not metric_cols:
        print("⚠️ Nenhuma métrica encontrada para gerar o relatório sintético.")
        return

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 📊 Relatório Sintético de Qualidade (RAGAS)\n\n")
        
        f.write("## 📈 Médias Globais da Bateria\n")
        f.write("Visão macro da qualidade da orquestração RAG e inferência LLM.\n\n")
        
        for m in metric_cols:
            mean_val = df[m].mean()
            f.write(f"- **{m.replace('_', ' ').title()}**: {mean_val:.4f}\n")
        
        f.write("\n---\n\n")
        
        f.write("## 🚨 Análise de Casos Críticos (Piores Scores)\n")
        f.write("Consultas que exigem revisão de prompt, otimização de retrieval ou troca de modelo.\n\n")
        
        # Identifica a pior resposta para cada métrica
        for m in metric_cols:
            worst_row = df.loc[df[m].idxmin()]
            f.write(f"### Pior performance em `{m}` (Score: {worst_row[m]:.4f})\n")
            f.write(f"- **Pergunta:** {worst_row['question']}\n")
            f.write(f"- **Resposta Gerada:** {worst_row['answer']}\n")
            if 'latencia_total_s' in df.columns:
                f.write(f"- **Latência:** {worst_row['latencia_total_s']:.2f}s\n")
            f.write("\n")


if __name__ == "__main__":
    run_ragas_evaluation()