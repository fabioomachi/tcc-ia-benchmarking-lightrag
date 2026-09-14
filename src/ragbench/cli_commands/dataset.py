"""Comando `generate-dataset`: golden dataset adversarial a partir dos POPs."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from ragbench.cli_commands import deps
from ragbench.evaluation.question_generator import GoldenDatasetGenerator


def generate_dataset(
    questions_per_doc: Annotated[int, typer.Option(help="Perguntas por documento")] = 2,
    output: Annotated[Path | None, typer.Option(help="Arquivo de saída")] = None,
) -> None:
    """Gera um Golden Dataset de perguntas situacionais adversariais baseadas nos POPs."""
    settings = deps.get_settings()
    out_file = output or (settings.questions_dir / "golden_dataset.json")

    async def _run_gen():
        generator = GoldenDatasetGenerator(settings=settings)
        return await generator.generate_dataset(
            output_file=out_file, questions_per_doc=questions_per_doc
        )

    deps.console.print(
        f"[bold blue]Gerando dataset adversarial ({questions_per_doc} perguntas/doc)...[/bold blue]"
    )
    dataset = asyncio.run(_run_gen())
    deps.console.print(
        f"[bold green]✅ Sucesso: {len(dataset)} perguntas geradas em {out_file}[/bold green]"
    )
