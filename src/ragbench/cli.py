"""CLI `ragbench`: registra os comandos implementados em `cli_commands`."""

import typer

from ragbench.cli_commands import chat_cmd, dataset, eval_cmd, health, index_cmd, run_cmd

app = typer.Typer(
    name="ragbench",
    help="Framework de benchmarking avançado para arquiteturas RAG (LightRAG) e avaliação via RAGAS.",
    add_completion=False,
)

app.command("health")(health.check_health)
app.command("index")(index_cmd.index_documents)
app.command("generate-dataset")(dataset.generate_dataset)
app.command("run")(run_cmd.run_benchmark)
app.command("eval")(eval_cmd.evaluate_run)
app.command("chat")(chat_cmd.interactive_chat)


if __name__ == "__main__":
    app()
