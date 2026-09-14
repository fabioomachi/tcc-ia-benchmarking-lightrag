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

    @classmethod
    def generate_execution_markdown_report(
        cls, records: list[QueryExecutionRecord], output_path: Path
    ) -> Path:
        # Garante conversão segura dos objetos Pydantic/dataclass para dict
        data = [rec.model_dump() if hasattr(rec, "model_dump") else rec.__dict__ for rec in records]
        df = pd.DataFrame(data)

        if df.empty:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                "# Resumo do Benchmark\n\nNenhum registro encontrado.", encoding="utf-8"
            )
            return output_path

        total_queries = len(df)

        # Tratamento defensivo caso a coluna 'status' venha com o objeto Enum ou nome diferente
        if "status" in df.columns:
            # Extrai o valor do Enum caso esteja serializado como objeto
            df["status_str"] = df["status"].apply(lambda x: getattr(x, "value", str(x)).lower())
            success_queries = len(df[df["status_str"] == "success"])
        else:
            success_queries = total_queries

        if "source" in df.columns:
            df["source_str"] = df["source"].apply(lambda x: getattr(x, "value", str(x)).lower())
            cache_hits = len(df[df["source_str"] == "semantic_cache"])
            engine_queries = len(df[df["source_str"] == "lightrag_engine"])
        else:
            cache_hits = 0
            engine_queries = total_queries

        mean_latency = (
            df["total_latency_seconds"].mean() if "total_latency_seconds" in df.columns else 0.0
        )

        if "ttft_seconds" in df.columns:
            ttft_series = df["ttft_seconds"].dropna()
            mean_ttft = ttft_series.mean() if not ttft_series.empty else 0.0
        else:
            mean_ttft = 0.0

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
                    str(row.get("query")).replace("\n", " ")[:60] + "..."
                    if len(str(row.get("query"))) > 60
                    else row.get("query")
                )
                ans = (
                    str(row.get("response", "")).replace("\n", " ")[:80] + "..."
                    if len(str(row.get("response", ""))) > 80
                    else str(row.get("response", ""))
                )
                ttft_val = (
                    f"{row.get('ttft_seconds'):.3f}s"
                    if pd.notnull(row.get("ttft_seconds"))
                    else "N/A"
                )
                latency_val = row.get("total_latency_seconds", 0.0) or 0.0
                f.write(
                    f"| {row.get('index')} | `{row.get('source')}` | `{row.get('mode')}` | {latency_val:.3f}s | {ttft_val} | `{row.get('status')}` | {q} | {ans} |\n"
                )

        return output_path

    @staticmethod
    def generate_ragas_markdown_report(df: pd.DataFrame, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if df.empty:
            output_path.write_text(
                "# 📊 Relatório de Qualidade RAGAS (LLM-as-a-Judge)\n\nNenhum dado avaliado.",
                encoding="utf-8",
            )
            return output_path
        metric_cols = [
            c
            for c in ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]
            if c in df.columns
        ]

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# 📊 Relatório de Qualidade RAGAS (LLM-as-a-Judge)\n\n")
            f.write("## 📈 Métricas Consolidadas Globais\n\n")

            if not metric_cols or df.empty:
                f.write("_Sem scores válidos (nenhuma métrica ou dataset vazio)._\n")
                return output_path

            for m in metric_cols:
                mean_val = df[m].mean()
                if pd.isna(mean_val):
                    f.write(
                        f"- **{m.replace('_', ' ').title()}**: `N/A` (todos os jobs falharam)\n"
                    )
                else:
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
                valid = df[m].dropna()
                if valid.empty:
                    f.write(f"### `{m}`: sem scores válidos (todos NaN — jobs falharam)\n\n")
                    continue
                worst_idx = valid.idxmin()
                worst_row = df.loc[worst_idx]
                f.write(f"### Pior score em `{m}` (`{worst_row[m]:.4f}`)\n")
                f.write(f"- **Tipo:** `{worst_row.get('question_type', 'N/A')}`\n")
                f.write(f"- **Pergunta:** {worst_row.get('question')}\n")
                f.write(f"- **Resposta:** {worst_row.get('answer')}\n")
                f.write(f"- **Ground Truth:** {worst_row.get('ground_truth', 'N/A')}\n\n")

        return output_path
