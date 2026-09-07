import json
import pandas as pd
from pathlib import Path
from datasets import Dataset

from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_recall,
    context_precision
)

from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings

# ---------------------------------------------------------
# Configuração de Caminhos
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).parent.name == "src" else Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "logs" / "benchmark_execution.log"
GOLDEN_DATASET_FILE = BASE_DIR / "dataset" / "golden_dataset.json"
RESULT_DIR = BASE_DIR / "resultados"
RESULT_DIR.mkdir(exist_ok=True)

def load_data_integrated():
    """Cruza o Golden Dataset gerado com as execuções capturadas nos logs do LightRAG."""
    if not LOG_FILE.exists():
        raise FileNotFoundError(f"Arquivo de log não encontrado em: {LOG_FILE}")
    
    # Carrega Ground Truth de referência se disponível
    golden_map = {}
    if GOLDEN_DATASET_FILE.exists():
        with open(GOLDEN_DATASET_FILE, "r", encoding="utf-8") as f:
            golden_data = json.load(f)
            golden_map = {item["question"].strip(): item for item in golden_data}

    questions, answers, contexts, ground_truths, question_types = [], [], [], [], []
    prompts_cache = {}

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): 
                continue
            try:
                event = json.loads(line)
                event_type = event.get("event_type")
                data = event.get("data", {})

                # Mapeia prompts brutos e contextos
                if event_type == "llm_input_prompt":
                    prompts_cache[data.get("raw_prompt_payload", "").strip()] = data.get("system_prompt", "")

                elif event_type == "interaction_record" and data.get("source") == "lightrag_engine":
                    query = data.get("user_query", "").strip()
                    response = data.get("final_response", "")
                    
                    # Recupera o contexto extraído pelo LightRAG
                    context_text = prompts_cache.get(query, "Sem contexto explícito capturado no log.")

                    # Faz a correspondência com o Golden Dataset para trazer a ground_truth
                    golden_item = golden_map.get(query, {})
                    gt = golden_item.get("ground_truth", "N/A")
                    q_type = golden_item.get("question_type", "UNMAPPED")

                    questions.append(query)
                    answers.append(response)
                    contexts.append([context_text])
                    ground_truths.append(gt)
                    question_types.append(q_type)

            except json.JSONDecodeError:
                continue

    return {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
        "question_type": question_types
    }

def run_ragas_evaluation():
    print("🔄 Carregando dados integrados (Logs + Golden Dataset)...")
    raw_data = load_data_integrated()

    if not raw_data["question"]:
        print("⚠️ Nenhum registro da 'lightrag_engine' encontrado nos logs para avaliação.")
        return

    dataset = Dataset.from_dict(raw_data)
    print(f"✅ Total de amostras prontas para avaliação no RAGAS: {len(dataset)}")

    print("🤖 Configurando LLM Judge (ChatOllama: qwen2.5:3b) e Embeddings (all-minilm)...")
    evaluator_llm = ChatOllama(model="qwen2.5:3b", base_url="http://localhost:11434", temperature=0.0)
    evaluator_embeddings = OllamaEmbeddings(model="all-minilm", base_url="http://localhost:11434")

    print("📊 Executando bateria de avaliação RAGAS...")
    try:
        results = evaluate(
            dataset=dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_recall,
                context_precision
            ],
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
            raise_exceptions=False
        )
    except Exception as e:
        print(f"❌ Falha crítica na orquestração do RAGAS: {e}")
        return

    df_ragas = results.to_pandas()
    
    # Merge com métricas de performance (Latência/TTFT)
    analise_detalhada_path = RESULT_DIR / "benchmark_analise_detalhada.csv"
    if analise_detalhada_path.exists():
        df_performance = pd.read_csv(analise_detalhada_path)
        # Sanitização de chaves para evitar desalinhamento no join
        df_ragas['question_clean'] = df_ragas['question'].str.strip()
        df_performance['pergunta_clean'] = df_performance['pergunta'].str.strip()
        
        df_final = pd.merge(
            df_ragas, 
            df_performance, 
            left_on="question_clean", 
            right_on="pergunta_clean", 
            how="left"
        )
        df_final.drop(columns=["question_clean", "pergunta_clean", "pergunta"], inplace=True, errors="ignore")
    else:
        df_final = df_ragas

    output_csv = RESULT_DIR / "ragas_evaluation_results.csv"
    df_final.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"\n✅ Relatório integrado exportado para: {output_csv}")

    report_md = RESULT_DIR / "resumo_qualidade_ragas.md"
    generate_synthetic_report(df_final, report_md)
    print(f"✅ Relatório sintético gerado em: {report_md}")    

def generate_synthetic_report(df: pd.DataFrame, output_path: Path):
    metric_cols = [col for col in ['faithfulness', 'answer_relevancy', 'context_recall', 'context_precision'] if col in df.columns]
    
    if not metric_cols:
        print("⚠️ Nenhuma métrica RAGAS encontrada para compor o relatório.")
        return

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 📊 Relatório Executivo de Qualidade RAG (RAGAS)\n\n")
        
        f.write("## 📈 Métricas Globais\n")
        for m in metric_cols:
            mean_val = df[m].mean()
            f.write(f"- **{m.replace('_', ' ').title()}**: `{mean_val:.4f}`\n")
        
        if "question_type" in df.columns:
            f.write("\n### 🏷️ Desempenho por Categoria de Complexidade\n\n")
            grouped = df.groupby("question_type")[metric_cols].mean()
            
            # Formatação manual de tabela Markdown sem dependência do tabulate
            headers = ["Tipo Pergunta"] + [m.replace('_', ' ').title() for m in metric_cols]
            f.write("| " + " | ".join(headers) + " |\n")
            f.write("| " + " | ".join(["---"] * len(headers)) + " |\n")
            
            for idx, row in grouped.iterrows():
                scores = [f"`{val:.4f}`" if pd.notna(val) else "N/A" for val in row]
                f.write(f"| {idx} | " + " | ".join(scores) + " |\n")

        f.write("\n---\n\n## 🚨 Análise de Casos Críticos\n")
        for m in metric_cols:
            worst_idx = df[m].idxmin()
            if pd.notna(worst_idx):
                worst_row = df.loc[worst_idx]
                f.write(f"### Pior performance em `{m}` (Score: {worst_row[m]:.4f})\n")
                f.write(f"- **Tipo:** `{worst_row.get('question_type', 'N/A')}`\n")
                f.write(f"- **Pergunta:** {worst_row['question']}\n")
                f.write(f"- **Resposta Gerada:** {worst_row['answer']}\n")
                f.write(f"- **Ground Truth:** {worst_row.get('ground_truth', 'N/A')}\n\n")

if __name__ == "__main__":
    run_ragas_evaluation()