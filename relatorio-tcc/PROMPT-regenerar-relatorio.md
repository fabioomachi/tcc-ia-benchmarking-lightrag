# PROMPT — Regenerar o relatório comparativo 2 vs 8 POPs

> Cole este prompt em uma nova sessão do agente para regenerar
> `relatorio-tcc/relatorio-2-vs-8-pops.md`, o gráfico e as evidências do zero.

---

Você está no repositório `ragbench` (raiz do projeto). Regenere o relatório comparativo
do TCC sobre o efeito do crescimento do corpus (2 → 8 POPs) nos braços RAG, seguindo
exatamente estes passos:

## 1. Mapeamento braço × conjunto (atualize se houver novos runs)

| Conjunto | POPs | Braço | Run (pasta em `runs/`) |
|---|---|---|---|
| `2pops-24` | 2 | Grafo `hybrid/k5`, pergunta completa | `exp_baseline_hypothesis` |
| `2pops-24` | 2 | Incompleta + clarify fixo (≤3 turnos) + grafo `hybrid/k5` | `exp_clarify_24` |
| `2pops-24` | 2 | Incompleta + clarify guiado + rota por documento | `exp_routed_24` |
| `2pops-24` | 2 | Só LLM, pergunta completa (zero retrieval) | `exp_direct_completa` |
| `2pops-24` | 2 | Árvore de decisão (regras fixas) | `exp_tree_24` |
| `8pops-16` | 8 | Grafo `hybrid/k5`, pergunta completa | `golden_full_hybrid` |
| `8pops-16` | 8 | Incompleta + clarify fixo (≤3 turnos) + grafo `hybrid/k5` | `golden_clarify_fixo` |
| `8pops-16` | 8 | Incompleta + clarify guiado + rota por documento | `golden_routed` |
| `8pops-16` | 8 | Só LLM, pergunta completa (zero retrieval) | `golden_direct_completa` |
| `8pops-16` | 8 | Árvore de decisão v2 | `golden_tree_v2` |
| `8pops-96` | 8 | Grafo `hybrid/k5`, pergunta completa | `golden_full_hybrid_96` |
| `8pops-96` | 8 | Incompleta + clarify fixo (≤3 turnos) + grafo `hybrid/k5` | `golden_clarify_fixo` |
| `8pops-96` | 8 | Incompleta + clarify guiado + rota por documento | `golden_routed` |
| `8pops-96` | 8 | Só LLM, pergunta completa (zero retrieval) | `golden_direct_completa_96` |
| `8pops-96` | 8 | Árvore de decisão v2 | `golden_tree_v2` |
| `2pops-24-v2` | 2 | Incompleta + clarify fixo (roteador off) | `exp_clarify_fixo_v2_24` |
| `2pops-24-v2` | 2 | Incompleta + clarify guiado + rota N-POPs | `exp_routed_v2_24` |
| `2pops-24-v2` | 2 | Árvore de decisão | `exp_tree_v2_24` |
| `8pops-96-v2` | 8 | Incompleta + clarify fixo (roteador off) | `golden_clarify_fixo_v2` |
| `8pops-96-v2` | 8 | Incompleta + clarify guiado + rota N-POPs | `golden_routed_v2` |
| `8pops-96-v2` | 8 | Árvore de decisão v2 | `golden_tree_v2` |

Atenção: `golden_clarify_fixo`, `golden_routed` e `golden_tree_v2` foram
**re-executados**: `runs/` guarda só o `n=96`; o nível `n=16` vive apenas em
`relatorio-tcc/evidencias/era8_16_*` (não sobrescrever). A série v2 (roteador
N-POPs, 06–09/10/2026) usa os mesmos cenários-fonte; seus CSVs vivem em
`evidencias/erav2_*` e suas linhas na tabela-fonte usam `conjunto` =
`2pops-24-v2` / `8pops-96-v2`. Notas v2: faithfulness da árvore nos 96 é média
sobre 79/96 (17 NaN por template curto); roteador off não gera `rota_*`
(`rota_doc: null` no manifest).

Cenários-fonte: `data/hypothesis_inicial_scenarios.json` (2 POPs, 24 cenários:
12 `pop_acesso_pf.md` + 12 `pop_cdc_pf.md`), `data/golden_scenarios_completa.json`
(8 POPs, 96 golden finais `golden96-00`…`golden96-95`, 12 por POP) e o snapshot
`relatorio-tcc/evidencias/cenarios_8pops_16.json` (16 golden intermediárias).
Juiz RAGAS: `gemini-3.5-flash-lite` nos três conjuntos.

## 2. Extração das métricas (só leitura, não reexecute runs/evals)

Para cada run da tabela acima, extraia de `runs/<id>/resumo_qualidade_ragas.md`
(seção "Métricas Consolidadas Globais") as 4 métricas: **faithfulness**,
**answer_relevancy**, **context_recall**, **context_precision**. Extraia `n` e a
latência média de `runs/<id>/benchmark_analise_detalhada.csv`
(coluna `total_latency_seconds`; conte linhas lógicas via `csv.DictReader`,
não `wc -l` — os campos contêm quebras de linha). Para o nível `8pops-16` de
clarify/routed/tree, use os CSVs versionados em `evidencias/era8_16_*_ragas.csv`
(runs não versionados).

## 3. Gráfico

Gere `relatorio-tcc/comparacao_2_vs_8_pops.png` com matplotlib (já em
`pyproject.toml`): figura 2×2 (um painel por métrica), em cada painel barras
agrupadas dos 5 braços × 3 conjuntos, valores rotulados nas barras, título citando o
juiz. Escreva o script gerador em `/tmp` (não poluir o repo) e execute com
`uv run python /tmp/<script>.py`.

## 4. Relatório

(Re)escreva `relatorio-tcc/relatorio-2-vs-8-pops.md` com:

1. Cabeçalho: conjuntos, POPs, cenários, juiz.
2. Referência ao PNG do passo 3.
3. **Matriz em 3 níveis** (nível = conjunto: `2pops-24`, `8pops-16`, `8pops-96`) com
   colunas: Braço | Run | n | Faithfulness | Answer Relevancy | Context Recall |
   Context Precision | Lat. média.
4. Seção "O que aconteceu": colapso parcial do grafo puro, mitigação do roteamento,
   clarify real no 96 (1.44/1.24 turnos) vs 0 turnos no 16,
   resistência da árvore, piso do só-LLM, recall/precision perto do teto.
5. Seção de experimentos de tuning revertidos, se houver (descrever o que foi
   testado, números antes/depois, decisão).
6. Ameaças à validade: conjuntos de perguntas diferentes, N assimétrico no
   baseline (`n=4`), `incompleta == completa`/slots vazios no nível 16,
   cache-hit de LLM nas latências do nível 16 vs 0% no 96,
   variação do juiz (~±0.05), run-ids `*_96` novos.
7. Lista dos arquivos de `evidencias/`.

## 5. Evidências

Copie para `relatorio-tcc/evidencias/` (sobrescrevendo): os
`runs/<id>/ragas_evaluation_results.csv` como `era2_<braco>_ragas.csv` /
`era8_<braco>_ragas.csv` (n=96) / `era8_96_hybrid_ragas.csv` /
`era8_96_direct_ragas.csv` (braco ∈ hybrid, clarify_fixo, routed, direct, tree);
para a série v2, `erav2_24_<braco>_ragas.csv` / `erav2_96_<braco>_ragas.csv`
(braco ∈ clarify_fixo, routed, tree) + `*_manifest.json` correspondentes;
**preservar** `era8_16_*_ragas.csv` + `cenarios_8pops_16.json` (nível intermediário);
os manifests `clarify_manifest.json` / `tree_manifest.json` / `direct_manifest.json`
disponíveis; os JSONs de cenários como `cenarios_2pops.json` / `cenarios_8pops.json`
(+ `cenarios_8pops_16.json` preservado).
Gere `tabela_bracos_2_vs_8.csv` com o cabeçalho
`conjunto,pops,braco,run,n,faithfulness,answer_relevancy,context_recall,context_precision,lat_media_s`.

## 6. Validação final

Confirme: PNG existe e é válido; contagens lógicas dos CSVs copiados batem com os
`n` da matriz (4/24/16/96); coluna `conjunto` presente na tabela-fonte;
números idênticos entre tabela-fonte e markdown. Não altere nada
em `src/` (sem ruff/pytest necessário). Resuma em português com a tabela antes/depois.
