import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from ragbench.config import settings
from ragbench.core.models import SearchMode
from ragbench.engines.lightrag_engine import LightRAGEngine
from ragbench.evaluation.question_generator import GoldenDatasetGenerator
from ragbench.evaluation.ragas_evaluator import RagasEvaluator
from ragbench.infrastructure.semantic_cache import SemanticCache, SlidingWindowHistory
from ragbench.infrastructure.storage import SQLiteExecutionStorage
from ragbench.reporting.reporters import BenchmarkReporter
from ragbench.runner import BenchmarkRunner

app = typer.Typer(
    name="ragbench",
    help="Framework de benchmarking avançado para arquiteturas RAG (LightRAG) e avaliação via RAGAS.",
    add_completion=False,
)
console = Console()


@app.command("health")
def check_health():
    """Verifica a conectividade com o Ollama local e status dos modelos."""
    from ragbench.infrastructure.ollama_client import ResilientOllamaClient

    client = ResilientOllamaClient(settings.ollama)
    is_up = asyncio.run(client.check_health())
    if is_up:
        console.print("[green]✔ Ollama operacional e respondendo na porta local.[/green]")
    else:
        console.print(f"[red]✖ Falha ao conectar ao Ollama em {settings.ollama.base_url}[/red]")
        sys.exit(1)


@app.command("index")
def index_documents(
    pops_dir: Annotated[Path | None, typer.Option(help="Diretório com arquivos POPs .txt")] = None,
    clean: Annotated[bool, typer.Option(help="Limpa o banco de grafos antes de indexar")] = True,
):
    """Indexa documentos POP no banco de grafos e vetores do LightRAG."""
    target_dir = pops_dir or settings.pops_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    storage_dir = settings.storage_dir

    if clean and storage_dir.exists():
        import shutil

        console.print("[yellow]Higienizando banco de grafos anterior...[/yellow]")
        shutil.rmtree(storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)

    txt_files = list(target_dir.glob("*.txt"))
    if not txt_files:
        console.print(
            "[yellow]Nenhum arquivo encontrado. Criando POPs sintéticos padrão...[/yellow]"
        )
        pop_pix = target_dir / "pop_cancelamento_pix.txt"
        pop_pix.write_text(
            "PROCEDIMENTO OPERACIONAL PADRÃO - POP-014: Cancelamento de PIX por Suspeita de Fraude.\n"
            "1. O operador deve validar a identidade do cliente via biometria facial no sistema BioCheck.\n"
            "2. Caso haja contestação por golpe do falso leilão, o bloqueio cautelar deve ser acionado no sistema MED (Mecanismo Especial de Devolução) do BACEN em até 30 minutos corridos após a denúncia.\n"
            "3. EXCEÇÃO: É estritamente proibido o estorno manual sem a autorização prévia, registrada em ticket, da mesa de compliance antifraude.\n"
            "4. Falhas na aplicação do bloqueio cautelar no prazo regulatório geram passivo ao banco de acordo com a resolução BCB nº 103.",
            encoding="utf-8",
        )
        pop_cartao = target_dir / "pop_bloqueio_cartao.txt"
        pop_cartao.write_text(
            "PROCEDIMENTO OPERACIONAL PADRÃO - POP-015: Bloqueio de Cartão de Crédito por Suspeita de Fraude.\n"
            "1. O operador deve verificar o padrão de compras no sistema de monitoramento transacional.\n"
            "2. Em caso de transações internacionais atípicas consecutivas, acionar o bloqueio preventivo do cartão.\n"
            "3. CONDICAO: O bloqueio preventivo exige a comunicação imediata ao cliente via SMS e e-mail cadastrado, conforme determina a norma do BACEN sobre transparência.\n"
            "4. O desbloqueio só pode ser realizado após contato ativo do cliente validado pelo sistema BioCheck.",
            encoding="utf-8",
        )
        txt_files = list(target_dir.glob("*.txt"))

    console.print(f"[bold blue]Iniciando indexação de {len(txt_files)} documentos...[/bold blue]")

    async def _run_index():
        engine = LightRAGEngine(settings=settings)
        await engine.initialize()

        for doc in txt_files:
            console.print(f" -> Indexando: [cyan]{doc.name}[/cyan] ...")
            raw_text = doc.read_text(encoding="utf-8")
            enriched = f"DOCUMENTO_ORIGEM: {doc.name}\n\n{raw_text}"
            try:
                await engine.ainsert(enriched)
                console.print(f"    [green]✔ {doc.name} inserido no grafo.[/green]")
            except Exception as e:
                console.print(f"    [red]✖ Falha em {doc.name}: {e}[/red]")

        await engine.finalize()

    asyncio.run(_run_index())
    console.print("[bold green]✅ Indexação de documentos concluída com sucesso![/bold green]")


@app.command("generate-dataset")
def generate_dataset(
    questions_per_doc: Annotated[int, typer.Option(help="Perguntas por documento")] = 2,
    output: Annotated[Path | None, typer.Option(help="Arquivo de saída")] = None,
):
    """Gera um Golden Dataset de perguntas situacionais adversariais baseadas nos POPs."""
    out_file = output or (settings.questions_dir / "golden_dataset.json")

    async def _run_gen():
        generator = GoldenDatasetGenerator(settings=settings)
        return await generator.generate_dataset(
            output_file=out_file, questions_per_doc=questions_per_doc
        )

    console.print(
        f"[bold blue]Gerando dataset adversarial ({questions_per_doc} perguntas/doc)...[/bold blue]"
    )
    dataset = asyncio.run(_run_gen())
    console.print(
        f"[bold green]✅ Sucesso: {len(dataset)} perguntas geradas em {out_file}[/bold green]"
    )


@app.command("run")
def run_benchmark(
    target: Annotated[Path | None, typer.Option(help="Arquivo ou pasta de perguntas")] = None,
    mode: Annotated[
        str, typer.Option(help="Modo de busca (naive, local, global, hybrid)")
    ] = "hybrid",
    top_k: Annotated[int, typer.Option(help="Top-K entidades e chunks recuperados")] = 5,
    concurrency: Annotated[int, typer.Option(help="Requisições concorrentes ao Ollama")] = 10,
    resume: Annotated[bool, typer.Option(help="Retoma de checkpoint anterior")] = True,
    run_name: Annotated[str | None, typer.Option(help="Nome identificador da execução")] = None,
):
    """Executa a bateria de testes de benchmark em lote com checkpointing e relatórios automáticos."""
    target_path = target or settings.questions_dir
    search_mode = SearchMode(mode)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = run_name or f"run_{timestamp}_{mode}"
    run_dir = settings.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    db_path = run_dir / "checkpoint.sqlite3"
    storage = SQLiteExecutionStorage(db_path)

    async def _run():
        queries = BenchmarkRunner.load_queries_from_path(target_path)
        if not queries:
            console.print(f"[yellow]Nenhuma pergunta encontrada em {target_path}[/yellow]")
            return

        engine = LightRAGEngine(settings=settings)
        await engine.initialize()

        runner = BenchmarkRunner(engine=engine, storage=storage, settings=settings)
        console.print(
            f"[bold blue]Disparando benchmark: {len(queries)} perguntas | Modo: {mode} | Concorrência: {concurrency}[/bold blue]"
        )

        records = await runner.execute_batch(
            queries=queries,
            mode=search_mode,
            top_k=top_k,
            concurrency=concurrency,
            resume=resume,
        )

        await engine.finalize()

        # Exportações automáticas
        csv_path = run_dir / "benchmark_analise_detalhada.csv"
        md_path = run_dir / "resumo_benchmark.md"
        BenchmarkReporter.export_execution_csv(records, csv_path)
        BenchmarkReporter.generate_execution_markdown_report(records, md_path)

        # Cópia para o diretório legado de resultados para compatibilidade
        settings.result_dir.mkdir(parents=True, exist_ok=True)
        BenchmarkReporter.export_execution_csv(
            records, settings.result_dir / "benchmark_analise_detalhada.csv"
        )
        BenchmarkReporter.generate_execution_markdown_report(
            records, settings.result_dir / "resumo_benchmark.md"
        )

        console.print("\n[bold green]✅ Execução finalizada![/bold green]")
        console.print(f"📁 Checkpoint SQLite: [cyan]{db_path}[/cyan]")
        console.print(f"📊 Relatório Markdown: [cyan]{md_path}[/cyan]")
        console.print(f"📑 Exportação CSV: [cyan]{csv_path}[/cyan]")

    asyncio.run(_run())


@app.command("eval")
def evaluate_run(
    run_id: Annotated[str | None, typer.Option(help="ID da run a avaliar")] = None,
    checkpoint: Annotated[Path | None, typer.Option(help="Caminho do checkpoint.sqlite3")] = None,
):
    """Executa a avaliação de qualidade LLM-as-a-Judge (RAGAS) em uma execução anterior."""
    if checkpoint:
        db_path = checkpoint
    elif run_id:
        db_path = settings.runs_dir / run_id / "checkpoint.sqlite3"
    else:
        # Pega a run mais recente
        runs = sorted(
            list(settings.runs_dir.glob("*/checkpoint.sqlite3")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not runs:
            console.print("[red]Nenhum checkpoint de benchmark encontrado para avaliar.[/red]")
            sys.exit(1)
        db_path = runs[0]

    console.print(f"[bold blue]Avaliando execuções de: {db_path}[/bold blue]")
    storage = SQLiteExecutionStorage(db_path)
    records = storage.load_all_records()

    evaluator = RagasEvaluator(settings=settings)
    df_results = evaluator.run_evaluation(records)

    out_csv = db_path.parent / "ragas_evaluation_results.csv"
    out_md = db_path.parent / "resumo_qualidade_ragas.md"
    df_results.to_csv(out_csv, index=False, encoding="utf-8-sig")
    BenchmarkReporter.generate_ragas_markdown_report(df_results, out_md)

    # Copia para pasta legada resultados/
    df_results.to_csv(
        settings.result_dir / "ragas_evaluation_results.csv", index=False, encoding="utf-8-sig"
    )
    BenchmarkReporter.generate_ragas_markdown_report(
        df_results, settings.result_dir / "resumo_qualidade_ragas.md"
    )

    console.print("[bold green]✅ Avaliação RAGAS concluída![/bold green]")
    console.print(f"📊 Relatório de Qualidade: [cyan]{out_md}[/cyan]")
    console.print(f"📑 Tabela CSV: [cyan]{out_csv}[/cyan]")


@app.command("chat")
def interactive_chat(
    mode: Annotated[str, typer.Option(help="Modo de busca")] = "hybrid",
    top_k: Annotated[int, typer.Option(help="Top-K entidades")] = 5,
):
    """Sessão conversacional interativa no terminal com streaming, cache semântico e telemetria."""
    search_mode = SearchMode(mode)
    cache = SemanticCache(threshold=settings.cache_threshold)
    history = SlidingWindowHistory(max_turns=settings.history_turns)

    async def _chat_loop():
        engine = LightRAGEngine(settings=settings)
        await engine.initialize()

        console.print(
            Panel(
                f"[bold green]ragbench Interactive Chat[/bold green]\n"
                f"Modo: [cyan]{mode}[/cyan] | Top-K: [cyan]{top_k}[/cyan] | Cache: [cyan]{settings.cache_threshold}[/cyan]\n"
                f"Digite [bold red]'sair'[/bold red] para encerrar.",
                title="Sessão Iniciada",
            )
        )

        while True:
            try:
                query = console.input("\n[bold yellow]Pergunta > [/bold yellow]").strip()
                if query.lower() in ["sair", "exit", "quit"]:
                    break
                if not query:
                    continue

                start_time = time.perf_counter()

                # Checagem de Cache Semântico
                query_embs = await engine.ollama_client.get_embeddings(
                    model=settings.lightrag.embed_model,
                    texts=[query],
                )
                if len(query_embs) > 0:
                    cached_resp, similarity = cache.get(query_embs[0])
                    if cached_resp:
                        latency = time.perf_counter() - start_time
                        console.print(
                            f"\n[green]⚡ Resposta (via Cache Semântico - Score: {similarity:.3f} | Latência: {latency:.3f}s):[/green]"
                        )
                        console.print(cached_resp)
                        history.add_turn(query, cached_resp)
                        continue

                # Chamada do RAG com Streaming
                console.print(f"\n[blue]🤖 Resposta Gerada ({mode}):[/blue]")
                response_gen = await engine.aquery(
                    query, mode=search_mode, top_k=top_k, stream=True
                )

                first_token = True
                ttft = 0.0
                full_text = ""

                async for chunk in response_gen:  # type: ignore
                    if first_token:
                        ttft = time.perf_counter() - start_time
                        first_token = False
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                    full_text += chunk

                total_latency = time.perf_counter() - start_time
                console.print(
                    f"\n\n[dim]⏱ Latência Total: {total_latency:.3f}s | TTFT: {ttft:.3f}s[/dim]"
                )

                if len(query_embs) > 0:
                    cache.add(query_embs[0], full_text)
                history.add_turn(query, full_text)

            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Erro no processamento: {e}[/red]")

        await engine.finalize()
        console.print("[yellow]Sessão encerrada com sucesso.[/yellow]")

    asyncio.run(_chat_loop())


if __name__ == "__main__":
    app()
