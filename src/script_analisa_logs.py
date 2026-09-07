import json
import logging
from pathlib import Path
import pandas as pd

# Setup de Caminhos
BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).parent.name == "src" else Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "logs" / "benchmark_execution.log"
RESULT_DIR = BASE_DIR / "resultados"

# Garante a criação da pasta 'resultados'
RESULT_DIR.mkdir(exist_ok=True)

def parse_benchmark_logs():
    if not LOG_FILE.exists():
        print(f"❌ Arquivo de log não encontrado em: {LOG_FILE}")
        return

    records = []
    prompts_map = {}

    print(f"🔍 Analisando logs em: {LOG_FILE}...")

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
                event_type = event.get("event_type")
                data = event.get("data", {})

                # Captura o prompt completo/contexto enviado ao LLM para vincular com a resposta
                if event_type == "llm_input_prompt":
                    raw_prompt = data.get("raw_prompt_payload", "")
                    sys_prompt = data.get("system_prompt", "")
                    prompts_map[data.get("timestamp", event.get("timestamp"))] = {
                        "system_prompt": sys_prompt,
                        "raw_prompt_payload": raw_prompt
                    }

                # Captura a interação final
                elif event_type == "interaction_record":
                    metrics = data.get("execution_metrics", {})
                    params = data.get("parameters", {})
                    
                    record = {
                        "data_hora": event.get("datetime"),
                        "pergunta": data.get("user_query"),
                        "resposta": data.get("final_response"),
                        "fonte": data.get("source"),
                        "score_similaridade_cache": data.get("similarity_score", None),
                        "latencia_total_s": metrics.get("total_latency_seconds"),
                        "latencia_rag_s": metrics.get("rag_retrieval_latency_seconds", None),
                        "ttft_s": metrics.get("ttft_seconds", None),
                        "modo_busca": params.get("search_mode"),
                        "top_k": params.get("top_k"),
                        "modelo_llm": params.get("model")
                    }
                    records.append(record)

            except json.JSONDecodeError:
                continue

    if not records:
        print("⚠️ Nenhum registro de interação ('interaction_record') encontrado nos logs.")
        return

    df = pd.DataFrame(records)

    # 1. Exportação CSV Completo para Análise de Dados
    csv_path = RESULT_DIR / "benchmark_analise_detalhada.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"✅ Análise detalhada salva em CSV: {csv_path}")

    # 2. Exportação de Relatório Executivo em Markdown
    md_path = RESULT_DIR / "resumo_benchmark.md"
    generate_markdown_report(df, md_path)
    print(f"✅ Relatório executivo salvo em MD: {md_path}")


def generate_markdown_report(df: pd.DataFrame, output_path: Path):
    total_interacoes = len(df)
    cache_hits = len(df[df["fonte"] == "semantic_cache"])
    engine_queries = len(df[df["fonte"] == "lightrag_engine"])
    
    media_latencia = df["latencia_total_s"].mean()
    df_engine = df[df["fonte"] == "lightrag_engine"]
    media_ttft = df_engine["ttft_s"].mean() if "ttft_s" in df_engine and not df_engine["ttft_s"].dropna().empty else 0

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 📊 Relatório de Benchmarking RAG\n\n")
        f.write("## 🛠️ Métricas Gerais de Execução\n\n")
        f.write(f"- **Total de Consultas Executadas:** {total_interacoes}\n")
        f.write(f"- **Consultas via LightRAG Engine:** {engine_queries}\n")
        f.write(f"- **Consultas via Semantic Cache (Hit):** {cache_hits}\n")
        f.write(f"- **Latência Média Total:** {media_latencia:.4f}s\n")
        if media_ttft:
            f.write(f"- **Time To First Token (TTFT) Médio:** {media_ttft:.4f}s\n")
        f.write("\n---\n\n")

        f.write("## 📝 Histórico de Respostas e Latência\n\n")
        f.write("| Data/Hora | Fonte | Modo | Latência Total | TTFT | Pergunta | Resposta |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")

        for _, row in df.iterrows():
            pergunta_corta = row["pergunta"].replace("\n", " ")[:60] + "..." if len(row["pergunta"]) > 60 else row["pergunta"]
            resposta_corta = str(row["resposta"]).replace("\n", " ")[:80] + "..." if len(str(row["resposta"])) > 80 else str(row["resposta"])
            ttft_val = f"{row['ttft_s']:.3f}s" if pd.notnull(row["ttft_s"]) else "N/A"
            
            f.write(f"| {row['data_hora']} | `{row['fonte']}` | `{row['modo_busca']}` | {row['latencia_total_s']:.3f}s | {ttft_val} | {pergunta_corta} | {resposta_corta} |\n")

if __name__ == "__main__":
    parse_benchmark_logs()