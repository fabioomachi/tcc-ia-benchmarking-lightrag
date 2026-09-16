"""Comando `probe-retrieval`: audita qual documento cada modo recupera.

Para cada cenário (query enriquecida via clarificação simulada) e cada modo
(naive/local/global/hybrid), busca SÓ o contexto (`only_need_context`, sem
geração LLM — barato) e classifica o documento dominante por marcadores.
Gera `runs/probe_<id>/retrieval_probe.{json,md}`.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from ragbench.cli_commands import deps
from ragbench.conversational.batch import load_scenarios, simulate_clarification
from ragbench.engines.lightrag_engine import LightRAGEngine
from ragbench.infrastructure.logging import setup_logging

WORST_IDS_DEFAULT = (
    "acesso_site_biometria_7dias,acesso_portador_adicional,"
    "acesso_sms_nao_cadastrada,acesso_sequestro_senha8,acesso_titular_solidario"
)

ACESSO_MARKERS = [
    "senha de 6",
    "senha de 8",
    "alfa code",
    "biometria",
    "código de acesso",
    "codigo de acesso",
    "conta de acesso",
    "senha-8",
    "titular",
    "solidár",
    "sms",
    "chip",
    "portador adicional",
    'bloqueio "u"',
    "bloqueio 'u'",
    "célula de segurança",
]
CDC_MARKERS = [
    "cdc",
    "consign",
    "boleto",
    "amortiza",
    "liquida",
    "limite especial",
    "reaverbação",
    "reaverbacao",
    "convênio",
    "convenio",
    "800020",
    "anc",
]


def classify_context(context: str) -> tuple[str, int, int]:
    """Classifica o contexto como acesso/cdc/empate por contagem de marcadores."""
    low = context.lower()
    acesso = sum(low.count(m) for m in ACESSO_MARKERS)
    cdc = sum(low.count(m) for m in CDC_MARKERS)
    if acesso > cdc:
        return "pop_acesso_pf.md", acesso, cdc
    if cdc > acesso:
        return "pop_cdc_pf.md", acesso, cdc
    return "empate", acesso, cdc


def probe_retrieval(
    scenarios: Annotated[Path | None, typer.Option(help="JSON de cenários")] = None,
    modes: Annotated[str, typer.Option(help="Modos separados por vírgula")] = (
        "hybrid,local,global,naive"
    ),
    top_k: Annotated[int, typer.Option(help="Top-K")] = 5,
    max_clarify_turns: Annotated[int, typer.Option(help="Max turnos de clarificação")] = 3,
    ids: Annotated[str, typer.Option(help="IDs separados por vírgula (vazio=todos)")] = (
        WORST_IDS_DEFAULT
    ),
    run_name: Annotated[str | None, typer.Option(help="Nome da probe")] = None,
) -> None:
    """Recupera contextos por modo e registra o documento dominante."""
    settings = deps.get_settings()
    scenarios_path = scenarios or (settings.questions_dir / "hypothesis_inicial_scenarios.json")
    if not scenarios_path.exists():
        alt = Path("data/hypothesis_inicial_scenarios.json")
        if alt.exists():
            scenarios_path = alt
    mode_list = [m.strip() for m in modes.split(",") if m.strip()]
    wanted = {i.strip() for i in ids.split(",") if i.strip()} if ids else set()
    run_id = run_name or f"probe_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    setup_logging(settings, run_id=run_id)
    probe_dir = settings.runs_dir / run_id
    probe_dir.mkdir(parents=True, exist_ok=True)

    async def _run():
        items = await asyncio.to_thread(load_scenarios, scenarios_path)
        if wanted:
            items = [it for it in items if it.get("id") in wanted]
        if not items:
            deps.console.print("[yellow]Nenhum cenário selecionado.[/yellow]")
            return
        engine = LightRAGEngine.for_chat(settings=settings)
        await engine.initialize()
        try:
            rows: list[dict] = []
            for item in items:
                enriched = simulate_clarification(
                    str(item.get("pergunta_incompleta", "")),
                    dict(item.get("slots_simulados", {})),
                    max_turns=max_clarify_turns,
                )[2]
                for mode in mode_list:
                    try:
                        ctx = await engine.aget_context(query=enriched, mode=mode, top_k=top_k)
                    except Exception as e:
                        rows.append(
                            {
                                "id": item.get("id"),
                                "esperado": item.get("source_document"),
                                "mode": mode,
                                "erro": f"{type(e).__name__}: {e}",
                            }
                        )
                        continue
                    predicted, n_acesso, n_cdc = classify_context(ctx or "")
                    rows.append(
                        {
                            "id": item.get("id"),
                            "esperado": item.get("source_document"),
                            "mode": mode,
                            "doc_previsto": predicted,
                            "acertou": predicted == item.get("source_document"),
                            "marcadores_acesso": n_acesso,
                            "marcadores_cdc": n_cdc,
                            "contexto_chars": len(ctx or ""),
                            "contexto_preview": (ctx or "")[:600].replace("\n", " "),
                        }
                    )
            out_json = probe_dir / "retrieval_probe.json"
            out_md = probe_dir / "retrieval_probe.md"
            await asyncio.to_thread(
                out_json.write_text,
                json.dumps(rows, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            lines = [
                "# 🔍 Probe de retrieval por modo",
                "",
                f"Cenários: {len(items)} | modos: {', '.join(mode_list)} | top_k={top_k}",
                "",
                "| Cenário | Esperado | Modo | Previsto | Acertou | acesso | cdc |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
            for r in rows:
                if "erro" in r:
                    lines.append(
                        f"| {r['id']} | {r['esperado']} | {r['mode']} | ERRO | ❌ | - | - |"
                    )
                else:
                    mark = "✅" if r["acertou"] else "❌"
                    lines.append(
                        f"| {r['id']} | {r['esperado']} | {r['mode']} | "
                        f"{r['doc_previsto']} | {mark} | {r['marcadores_acesso']} | "
                        f"{r['marcadores_cdc']} |"
                    )
            total = sum(1 for r in rows if "erro" not in r)
            hits = sum(1 for r in rows if r.get("acertou"))
            lines += ["", f"**Acerto global: {hits}/{total}**"]
            for mode in mode_list:
                m_rows = [r for r in rows if r.get("mode") == mode and "erro" not in r]
                m_hits = sum(1 for r in m_rows if r.get("acertou"))
                lines.append(f"- {mode}: {m_hits}/{len(m_rows)}")
            await asyncio.to_thread(out_md.write_text, "\n".join(lines), encoding="utf-8")
            deps.console.print("\n[bold green]✅ probe finalizada![/bold green]")
            deps.console.print(f"📑 JSON: [cyan]{out_json}[/cyan]")
            deps.console.print(f"📊 MD: [cyan]{out_md}[/cyan]")
            deps.console.print(f"**Acerto global: {hits}/{total}**")
            for mode in mode_list:
                m_rows = [r for r in rows if r.get("mode") == mode and "erro" not in r]
                m_hits = sum(1 for r in m_rows if r.get("acertou"))
                deps.console.print(f"- {mode}: {m_hits}/{len(m_rows)}")
        finally:
            await engine.finalize()

    asyncio.run(_run())
