from pathlib import Path

import pandas as pd

from ragbench.core.models import QueryExecutionRecord


class BenchmarkReporter:
    """Gerador de relatórios executivos em Markdown e exportações analíticas CSV."""

    @staticmethod
    def export_execution_csv(records: list[QueryExecutionRecord], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = [r.model_dump() for r in records]
        df = pd.DataFrame(data)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        return output_path

    @staticmethod
    def generate_execution_markdown_report(
        records: list[QueryExecutionRecord], output_path: Path
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = [r.model_dump() for r in records]
        df = pd.DataFrame(data)

        total_queries = len(df)
        success_queries = len(df[df["status"] == "success"])
        cache_hits = len(df[df["source"] == "semantic_cache"])
        engine_queries = len(df[df["source"] == "lightrag_engine"])
        mean_latency = df["total_latency_seconds"].mean() if total_queries else 0.0

        ttft_series = df["ttft_seconds"].dropna()
        mean_ttft = ttft_series.mean() if not ttft_series.empty else 0.0

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# 📊 Relatório Executivo de Benchmarking RAG\n\n")
            f.write("## 🛠️ Métricas Gerais de Execução\n\n")
            f.write(f"- **Total de Consultas Submetidas:** {total_queries}\n")
            f.write(f"- **Consultas Concluídas com Sucesso:** {success_queries}\n")
            f.write(f"- **Consultas via LightRAG Engine:** {engine_queries}\n")
            f.write(f"- **Consultas via Semantic Cache (Hit):** {cache_hits}\n")
            f.write(
                f"- **Taxa de Cache Hit:** {(cache_hits / total_queries * 100) if total_queries else 0:.1f}%\n"
            )
            f.write(f"- **Latência Média Total:** {mean_latency:.4f}s\n")
            if mean_ttft:
                f.write(f"- **Time To First Token (TTFT) Médio:** {mean_ttft:.4f}s\n")
            f.write("\n---\n\n")

            f.write("## 📝 Amostra de Execuções e Latência\n\n")
            f.write(
                "| Índice | Fonte | Modo | Latência Total | TTFT | Status | Pergunta | Resposta |\n"
            )
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")

            for _, row in df.head(50).iterrows():
                q = (
                    str(row["query"]).replace("\n", " ")[:60] + "..."
                    if len(str(row["query"])) > 60
                    else row["query"]
                )
                ans = (
                    str(row["response"]).replace("\n", " ")[:80] + "..."
                    if len(str(row.get("response", ""))) > 80
                    else str(row.get("response", ""))
                )
                ttft_val = (
                    f"{row['ttft_seconds']:.3f}s" if pd.notnull(row.get("ttft_seconds")) else "N/A"
                )
                f.write(
                    f"| {row['index']} | `{row['source']}` | `{row['mode']}` | {row['total_latency_seconds']:.3f}s | {ttft_val} | `{row['status']}` | {q} | {ans} |\n"
                )

        return output_path

    @staticmethod
    def generate_ragas_markdown_report(df: pd.DataFrame, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        metric_cols = [
            c
            for c in ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]
            if c in df.columns
        ]

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# 📊 Relatório de Qualidade RAGAS (LLM-as-a-Judge)\n\n")
            f.write("## 📈 Métricas Consolidadas Globais\n\n")

            for m in metric_cols:
                mean_val = df[m].mean()
                f.write(f"- **{m.replace('_', ' ').title()}**: `{mean_val:.4f}`\n")

            if "question_type" in df.columns:
                f.write("\n### 🏷️ Desempenho por Categoria de Complexidade\n\n")
                grouped = df.groupby("question_type")[metric_cols].mean()

                headers = ["Tipo Pergunta"] + [m.replace("_", " ").title() for m in metric_cols]
                f.write("| " + " | ".join(headers) + " |\n")
                f.write("| " + " | ".join(["---"] * len(headers)) + " |\n")

                for idx, row in grouped.iterrows():
                    scores = [f"`{val:.4f}`" if pd.notna(val) else "N/A" for val in row]
                    f.write(f"| {idx} | " + " | ".join(scores) + " |\n")

            f.write("\n---\n\n## 🚨 Análise de Casos Críticos (Piores Desempenhos)\n")
            for m in metric_cols:
                worst_idx = df[m].idxmin()
                if pd.notna(worst_idx):
                    worst_row = df.loc[worst_idx]
                    f.write(f"### Pior score em `{m}` (`{worst_row[m]:.4f}`)\n")
                    f.write(f"- **Tipo:** `{worst_row.get('question_type', 'N/A')}`\n")
                    f.write(f"- **Pergunta:** {worst_row.get('question')}\n")
                    f.write(f"- **Resposta:** {worst_row.get('answer')}\n")
                    f.write(f"- **Ground Truth:** {worst_row.get('ground_truth', 'N/A')}\n\n")

        return output_path
