"""Amostragem pré-registrada do fatorial com índice condicionado (seed 42).

Desenho aninhado (64 IDs únicos in-domain + OOD-32 constante):
  denso-64 (mestre): 8/POP = 3 CONDITIONAL_WORKFLOW + 2 EDGE_CASE
                     + 2 ROLE_RESTRICTION + 1 REGULATORY_TIMELINE
  esparso-16: subconjunto do denso, 2/POP = 1 COND + 1 não-COND (rotação
              EDGE/ROLE/REG entre POPs)
  duo-16: fatia acesso+CDC do denso (8+8) — mesmo itemset em idx2 e idx8
  piloto-4: subconjunto do duo, 1 COND + 1 EDGE por doc (acesso, CDC)

Uso: python3 relatorio-tcc/evidencias/amostra_fatorial.py
Saídas: /tmp/cel_{piloto,duo16,esparso16,denso64}.json (cenários completos)
        /tmp/cel_{...}_target.json (sidecar [{"question": pergunta_completa}]
        para `ragbench run --target`, cujo loader só lê o campo "question")
        + relatorio-tcc/evidencias/amostra_fatorial_ids.json (anexo versionado)
"""

from __future__ import annotations

import json
import random
from pathlib import Path

SEED = 42
REPO = Path(__file__).resolve().parents[2]
GOLDEN = REPO / "data" / "golden_scenarios_completa.json"
OUT_IDS = Path(__file__).resolve().parent / "amostra_fatorial_ids.json"
TMP = Path("/tmp")

COND = "CONDITIONAL_WORKFLOW"
EDGE = "EDGE_CASE"
ROLE = "ROLE_RESTRICTION"
REG = "REGULATORY_TIMELINE"

DENSO_QUOTA = {COND: 3, EDGE: 2, ROLE: 2, REG: 1}  # 8/POP
# Segundo item do esparso por POP (o primeiro é sempre 1 COND).
ESPARSO_SEGUNDO = [EDGE, ROLE, REG, EDGE, ROLE, REG, EDGE, ROLE]
DUO_DOCS = ("pop_acesso_pf.md", "pop_cdc_pf.md")


def main() -> None:
    rng = random.Random(SEED)
    items = json.loads(GOLDEN.read_text(encoding="utf-8"))
    by_id = {it["id"]: it for it in items}
    assert len(by_id) == 96, f"golden96 esperado com 96 itens, achado {len(by_id)}"

    pops = sorted({it["source_document"] for it in items})
    assert len(pops) == 8, pops

    # --- denso-64 ---
    denso: list[str] = []
    for pop in pops:
        pool = sorted(it["id"] for it in items if it["source_document"] == pop)
        for tipo, k in DENSO_QUOTA.items():
            cand = [i for i in pool if by_id[i]["tipo"] == tipo]
            assert len(cand) >= k, f"{pop}/{tipo}: {len(cand)} < {k}"
            denso.extend(rng.sample(cand, k))
    assert len(set(denso)) == 64, len(set(denso))

    # --- esparso-16 (subset do denso) ---
    esparso: list[str] = []
    for pop, segundo in zip(pops, ESPARSO_SEGUNDO, strict=True):
        in_pop = [i for i in denso if by_id[i]["source_document"] == pop]
        cond = [i for i in in_pop if by_id[i]["tipo"] == COND]
        other = [i for i in in_pop if by_id[i]["tipo"] == segundo]
        assert cond and other, f"{pop}: sem {COND} ou {segundo} no denso"
        esparso.append(rng.choice(sorted(cond)))
        esparso.append(rng.choice(sorted(other)))
    assert len(set(esparso)) == 16 and set(esparso) <= set(denso)

    # --- duo-16 (fatia acesso+CDC do denso) ---
    duo = [i for i in denso if by_id[i]["source_document"] in DUO_DOCS]
    assert len(duo) == 16, len(duo)
    assert sum(1 for i in duo if by_id[i]["source_document"] == DUO_DOCS[0]) == 8
    assert sum(1 for i in duo if by_id[i]["source_document"] == DUO_DOCS[1]) == 8

    # --- piloto-4 (subset do duo) ---
    piloto: list[str] = []
    for doc in DUO_DOCS:
        in_doc = [i for i in duo if by_id[i]["source_document"] == doc]
        cond = sorted(i for i in in_doc if by_id[i]["tipo"] == COND)
        edge = sorted(i for i in in_doc if by_id[i]["tipo"] == EDGE)
        assert cond and edge, f"{doc}: sem COND ou EDGE no duo"
        piloto.append(rng.choice(cond))
        piloto.append(rng.choice(edge))
    assert len(set(piloto)) == 4 and set(piloto) <= set(duo)

    cells = {"piloto": piloto, "duo16": duo, "esparso16": esparso, "denso64": denso}
    for name, ids in cells.items():
        scenarios = [by_id[i] for i in sorted(ids)]
        (TMP / f"cel_{name}.json").write_text(
            json.dumps(scenarios, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        sidecar = [{"question": by_id[i]["pergunta_completa"]} for i in sorted(ids)]
        (TMP / f"cel_{name}_target.json").write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"cel_{name}: {len(ids)} itens -> /tmp/cel_{name}.json + _target.json")

    OUT_IDS.write_text(
        json.dumps({"seed": SEED, "cells": {k: sorted(v) for k, v in cells.items()}},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"anexo versionado: {OUT_IDS}")
    print(f"únicos in-domain: {len(set(denso))} (piloto⊂duo⊂denso, esparso⊂denso)")


if __name__ == "__main__":
    main()
