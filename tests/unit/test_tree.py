"""Árvore de decisão: um teste por ramo relevante dos POPs + protocolo."""

import json

import pytest
from typer.testing import CliRunner

from ragbench.cli import app
from ragbench.core.models import QueryInteractionSource, SearchMode
from ragbench.engines.decision_tree_engine import (
    FALLBACK_ANSWER,
    DecisionTreeEngine,
    decide,
    detect_doc,
)


@pytest.mark.parametrize(
    ("query", "branch", "doc"),
    [
        # Acesso
        (
            "senha 6 dígitos bloqueio 'U' tentando pelo site sem Alfa Code",
            "ACESSO_U_SITE_AGENCIA",
            "pop_acesso_pf.md",
        ),
        ("senha bloqueio 'U', como resolver?", "ACESSO_U_GERAL", "pop_acesso_pf.md"),
        ("senha 8 dígitos bloqueio '8', o que fazer?", "ACESSO_8_ALTERACAO", "pop_acesso_pf.md"),
        ("fui sequestrado, bloquear senha-8 do cartão", "ACESSO_SEQUESTRO_X98", "pop_acesso_pf.md"),
        ("marido bloqueou a senha, sou titular solidário", "ACESSO_SOLIDARIO", "pop_acesso_pf.md"),
        (
            "deficiente visual precisa de código de acesso?",
            "ACESSO_DEFICIENTE_CODIGO",
            "pop_acesso_pf.md",
        ),
        ("estou no exterior com bloqueio U", "ACESSO_EXTERIOR_U", "pop_acesso_pf.md"),
        ("cartão adicional do filho sem senha", "ACESSO_ADICIONAL", "pop_acesso_pf.md"),
        ("quero senha por SMS, não cadastrada", "ACESSO_SMS_ALTERACAO", "pop_acesso_pf.md"),
        ("troquei senha do cartão com chip e não funciona", "ACESSO_CHIP_TAA", "pop_acesso_pf.md"),
        ("apareceu código 'Q' após alterar no celular", "ACESSO_CODIGO_Q", "pop_acesso_pf.md"),
        ("não entro no App Alfa com senha do cartão", "ACESSO_CONTA_VS_SENHA8", "pop_acesso_pf.md"),
        ("bloqueio U, o SAC resolve?", "ACESSO_SAC_ALCADA_U", "pop_acesso_pf.md"),
        # CDC
        (
            "cancelar CDC renovação linha 2881 convênio 700001",
            "CDC_CANCEL_2881_DOC",
            "pop_cdc_pf.md",
        ),
        ("cancelar linha 2881 convênio 700017", "CDC_CANCEL_2881_C17", "pop_cdc_pf.md"),
        (
            "paguei boleto e debitou em conta, duplicidade",
            "CDC_DUPLICIDADE_BOLETO",
            "pop_cdc_pf.md",
        ),
        (
            "consignado INSS 900001 descontou em folha e conta",
            "CDC_CONSIG_DEVOLUCAO",
            "pop_cdc_pf.md",
        ),
        ("amortização linear no consignado", "CDC_LINEAR_VEDADO", "pop_cdc_pf.md"),
        ("operação em perdas, posso liquidar?", "CDC_PERDAS", "pop_cdc_pf.md"),
        ("ANC vencida sem limite, quero CDC", "CDC_ANC_SEM_LIMITE", "pop_cdc_pf.md"),
        (
            "não reconheço empréstimo do correspondente, fraude",
            "CDC_FRAUDE_CORRESPONDENTE",
            "pop_cdc_pf.md",
        ),
        ("cancelar Limite Especial usando", "CDC_LIMITE_CANCELAMENTO", "pop_cdc_pf.md"),
        ("CDC 13º vinculado ao aniversário", "CDC_13_ANIVERSARIO", "pop_cdc_pf.md"),
        ("antecipação IRPF e FGTS, quando debita?", "CDC_IRPF_FGTS", "pop_cdc_pf.md"),
        ("repactuação com Op pendente, cancela?", "CDC_REPACTUACAO", "pop_cdc_pf.md"),
        ("débito sem autorização após 01/03/2021", "CDC_AUTORIZACAO_2021", "pop_cdc_pf.md"),
    ],
)
def test_ramos(query, branch, doc):
    d = decide(query)
    assert d.branch == branch, f"{query!r} -> {d.branch}"
    assert d.doc == doc
    assert d.confident is True
    assert len(d.answer) > 50


def test_site_biometria_ok_vs_pendente():
    ok = decide("trocar senha pelo site sem Alfa Code, biometria há 10 dias")
    assert ok.branch == "ACESSO_SITE_BIOMETRIA_OK"
    pend = decide("trocar senha pelo site sem Alfa Code")
    assert pend.branch == "ACESSO_SITE_BIOMETRIA_PENDENTE"
    assert pend.confident is False


def test_fallback_para_fora_dos_pops():
    d = decide("qual a previsão do tempo amanhã?")
    assert d.branch in ("ESCLARECER", "FALLBACK")
    assert d.answer == FALLBACK_ANSWER or "preciso de um dado" in d.answer


def test_detect_doc_por_slots():
    assert detect_doc({"codigo_bloqueio": "U"}, "texto qualquer") == "pop_acesso_pf.md"
    assert detect_doc({}, "quero cancelar meu cdc e o boleto") == "pop_cdc_pf.md"
    assert detect_doc({}, "oi, tudo bem?") == ""


def test_engine_protocolo():
    import asyncio

    async def _run():
        from ragbench.config import BenchmarkSettings

        engine = DecisionTreeEngine(settings=BenchmarkSettings(_env_file=None))
        assert engine.llm_model.startswith("decision-tree")
        await engine.initialize()
        resp = await engine.aquery("senha bloqueio 'U'")
        assert isinstance(resp, str) and "U" in resp
        emb = await engine.get_query_embeddings(["x", "y"])
        assert emb.shape == (2, 3)
        await engine.ainsert("doc")
        await engine.finalize()

    asyncio.run(_run())


def test_run_tree_gera_artefatos_com_tree_engine(monkeypatch, tmp_path):
    import os

    from ragbench.cli_commands import deps
    from ragbench.config import BenchmarkSettings
    from ragbench.infrastructure.storage import SQLiteExecutionStorage

    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__", "ROUTING__")):
            monkeypatch.delenv(key, raising=False)
    settings = BenchmarkSettings(_env_file=None)
    settings.storage_dir = tmp_path / "graph"
    settings.runs_dir = tmp_path / "runs"
    settings.results_dir = tmp_path / "resultados"
    settings.questions_dir = tmp_path / "data"
    settings.questions_dir.mkdir(parents=True)
    monkeypatch.setattr(deps, "get_settings", lambda: settings)

    scenarios = [
        {
            "id": "s1",
            "pergunta_incompleta": "Minha senha bloqueou com código U",
            "slots_simulados": {"codigo_bloqueio": "U"},
            "ground_truth": "G",
            "tipo": "CONDITIONAL_WORKFLOW",
            "source_document": "pop_acesso_pf.md",
        }
    ]
    sc_path = settings.questions_dir / "hypothesis_inicial_scenarios.json"
    sc_path.write_text(json.dumps(scenarios), encoding="utf-8")

    result = CliRunner().invoke(app, ["run-tree", "--run-name", "t1"])
    assert result.exit_code == 0, result.output

    run_dir = settings.runs_dir / "t1"
    assert (run_dir / "checkpoint.sqlite3").exists()
    assert (run_dir / "tree_manifest.json").exists()
    assert (run_dir / "golden.json").exists()
    records = SQLiteExecutionStorage(run_dir / "checkpoint.sqlite3").load_all_records()
    assert records[0].mode == SearchMode.TREE
    assert records[0].source == QueryInteractionSource.TREE_ENGINE
    manifest = json.loads((run_dir / "tree_manifest.json").read_text(encoding="utf-8"))
    assert manifest[0]["branch"].startswith("ACESSO")


def test_run_tree_help():
    result = CliRunner().invoke(app, ["run-tree", "--help"])
    assert result.exit_code == 0
    assert "rvore" in result.output
