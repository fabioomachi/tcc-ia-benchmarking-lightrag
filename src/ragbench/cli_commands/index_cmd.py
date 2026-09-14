"""Comando `index`: indexação de POPs no grafo LightRAG."""

import asyncio
import shutil
from itertools import chain
from pathlib import Path
from typing import Annotated

import typer

from ragbench.cli_commands import deps
from ragbench.engines.lightrag_engine import LightRAGEngine

POP_PIX_CONTENT = (
    "PROCEDIMENTO OPERACIONAL PADRÃO - POP-014: Cancelamento de PIX por Suspeita de Fraude.\n"
    "1. O operador deve validar a identidade do cliente via biometria facial no sistema BioCheck.\n"
    "2. Caso haja contestação por golpe do falso leilão, o bloqueio cautelar deve ser acionado no sistema MED (Mecanismo Especial de Devolução) do BACEN em até 30 minutos corridos após a denúncia.\n"
    "3. EXCEÇÃO: É estritamente proibido o estorno manual sem a autorização prévia, registrada em ticket, da mesa de compliance antifraude.\n"
    "4. Falhas na aplicação do bloqueio cautelar no prazo regulatório geram passivo ao banco de acordo com a resolução BCB nº 103."
)

POP_CARTAO_CONTENT = (
    "PROCEDIMENTO OPERACIONAL PADRÃO - POP-015: Bloqueio de Cartão de Crédito por Suspeita de Fraude.\n"
    "1. O operador deve verificar o padrão de compras no sistema de monitoramento transacional.\n"
    "2. Em caso de transações internacionais atípicas consecutivas, acionar o bloqueio preventivo do cartão.\n"
    "3. CONDICAO: O bloqueio preventivo exige a comunicação imediata ao cliente via SMS e e-mail cadastrado, conforme determina a norma do BACEN sobre transparência.\n"
    "4. O desbloqueio só pode ser realizado após contato ativo do cliente validado pelo sistema BioCheck."
)


def discover_pop_files(target_dir: Path) -> list[Path]:
    """Lista POPs (.txt/.md) do diretório (puro: sem escrita)."""
    return list(chain(target_dir.glob("*.txt"), target_dir.glob("*.md")))


def seed_default_pops(target_dir: Path) -> list[Path]:
    """Cria os POPs sintéticos padrão e retorna os arquivos descobertos."""
    (target_dir / "pop_cancelamento_pix.txt").write_text(POP_PIX_CONTENT, encoding="utf-8")
    (target_dir / "pop_bloqueio_cartao.txt").write_text(POP_CARTAO_CONTENT, encoding="utf-8")
    return discover_pop_files(target_dir)


def index_documents(
    pops_dir: Annotated[Path | None, typer.Option(help="Diretório com arquivos POPs .txt")] = None,
    clean: Annotated[bool, typer.Option(help="Limpa o banco de grafos antes de indexar")] = True,
) -> None:
    """Indexa documentos POP no banco de grafos e vetores do LightRAG."""
    settings = deps.get_settings()
    target_dir = pops_dir or settings.pops_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    storage_dir = settings.storage_dir

    if clean and storage_dir.exists():
        deps.console.print("[yellow]Higienizando banco de grafos anterior...[/yellow]")
        shutil.rmtree(storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)

    txt_files = discover_pop_files(target_dir)

    if not txt_files:
        deps.console.print(
            "[yellow]Nenhum arquivo encontrado. Criando POPs sintéticos padrão...[/yellow]"
        )
        txt_files = seed_default_pops(target_dir)

    deps.console.print(
        f"[bold blue]Iniciando indexação de {len(txt_files)} documentos...[/bold blue]"
    )

    async def _run_index():
        engine = LightRAGEngine.for_index(settings=settings)
        await engine.initialize()

        for doc in txt_files:
            deps.console.print(f" -> Indexando: [cyan]{doc.name}[/cyan] ...")
            raw_text = doc.read_text(encoding="utf-8")
            enriched = f"DOCUMENTO_ORIGEM: {doc.name}\n\n{raw_text}"
            try:
                await engine.ainsert(enriched)
                deps.console.print(f"    [green]✔ {doc.name} inserido no grafo.[/green]")
            except Exception as e:
                deps.console.print(f"    [red]✖ Falha em {doc.name}: {e}[/red]")

        await engine.finalize()

    asyncio.run(_run_index())
    deps.console.print("[bold green]✅ Indexação de documentos concluída com sucesso![/bold green]")
