# PROMPT — Regenerar o relatório comparativo 2 vs 8 POPs

> Cole este prompt em uma nova sessão do agente para regenerar
> `relatorio-tcc/relatorio-2-vs-8-pops.md`, o gráfico e as evidências do zero.

---

Você está no repositório `ragbench` (raiz do projeto). Regenere o relatório comparativo
do TCC sobre o efeito do crescimento do corpus (2 → 8 POPs) nos braços RAG, seguindo
exatamente estes passos:

## 1. Mapeamento braço × era (atualize se houver novos runs)

| POPs | Braço | Run (pasta em `runs/`) |
|---|---|---|
| 2 | Grafo `hybrid/k5`, pergunta completa | `exp_baseline_hypothesis` |
| 2 | Incompleta + clarify fixo (≤3 turnos) + grafo `hybrid/k5` | `exp_clarify_24` |
| 2 | Incompleta + clarify guiado + rota por documento | `exp_routed_24` |
| 2 | Só LLM, pergunta completa (zero retrieval) | `exp_direct_completa` |
| 2 | Árvore de decisão (regras fixas) | `exp_tree_24` |
| 8 | Grafo `hybrid/k5`, pergunta completa | `golden_full_hybrid` |
| 8 | Incompleta + clarify fixo (≤3 turnos) + grafo `hybrid/k5` | `golden_clarify_fixo` |
| 8 | Incompleta + clarify guiado + rota por documento | `golden_routed` |
| 8 | Só LLM, pergunta completa (zero retrieval) | `golden_direct_completa` |
| 8 | Árvore de decisão v2 | `golden_tree_v2` |

Cenários-fonte: `data/hypothesis_inicial_scenarios.json` (era 2 POPs, 24 cenários:
12 `pop_acesso_pf.md` + 12 `pop_cdc_pf.md`) e `data/golden_scenarios_completa.json`
(era 8 POPs, 16 golden, 2 por POP). Juiz RAGAS: `gemini-3.5-flash-lite` nas duas eras.

## 2. Extração das métricas (só leitura, não reexecute runs/evals)

Para cada run da tabela acima, extraia de `runs/<id>/resumo_qualidade_ragas.md`
(seção "Métricas Consolidadas Globais") as 4 métricas: **faithfulness**,
**answer_relevancy**, **context_recall**, **context_precision**. Extraia `n` e a
latência média de `runs/<id>/benchmark_analise_detalhada.csv`
(coluna `total_latency_seconds`; conte linhas lógicas via `csv.DictReader`,
não `wc -l` — os campos contêm quebras de linha).

## 3. Gráfico

Gere `relatorio-tcc/comparacao_2_vs_8_pops.png` com matplotlib (já em
`pyproject.toml`): figura 2×2 (um painel por métrica), em cada painel barras
agrupadas dos 5 braços × 2 eras, valores rotulados nas barras, título citando o
juiz. Escreva o script gerador em `/tmp` (não poluir o repo) e execute com
`uv run python /tmp/<script>.py`.

## 4. Relatório

(Re)escreva `relatorio-tcc/relatorio-2-vs-8-pops.md` com:

1. Cabeçalho: eras, POPs, cenários, juiz.
2. Referência ao PNG do passo 3.
3. **Matriz em 2 níveis** (nível 1 = quantidade de POPs, nível 2 = braço) com
   colunas: Braço | Run | n | Faithfulness | Answer Relevancy | Context Recall |
   Context Precision | Lat. média.
4. Seção "O que aconteceu": colapso do grafo puro, mitigação do roteamento,
   imunidade da árvore, piso do só-LLM, saturação de recall/precision.
5. Seção de experimentos de tuning revertidos, se houver (descrever o que foi
   testado, números antes/depois, decisão).
6. Ameaças à validade: conjuntos de perguntas diferentes, N assimétrico no
   baseline, `incompleta == completa`/slots vazios nos golden, cache-hit de LLM
   nas latências, variação do juiz (~±0.05).
7. Lista dos arquivos de `evidencias/`.

## 5. Evidências

Copie para `relatorio-tcc/evidencias/` (sobrescrevendo): os 10
`runs/<id>/ragas_evaluation_results.csv` como `era2_<braco>_ragas.csv` /
`era8_<braco>_ragas.csv` (braco ∈ hybrid, clarify_fixo, routed, direct, tree);
os manifests `clarify_manifest.json` / `tree_manifest.json` / `direct_manifest.json`
disponíveis; os 2 JSONs de cenários como `cenarios_2pops.json` / `cenarios_8pops.json`.
Gere `tabela_bracos_2_vs_8.csv` com o cabeçalho
`pops,braco,run,n,faithfulness,answer_relevancy,context_recall,context_precision,lat_media_s`.

## 6. Validação final

Confirme: PNG existe e é válido; contagens lógicas dos CSVs copiados batem com os
`n` da matriz; números da tabela-fonte idênticos aos do markdown. Não altere nada
em `src/` (sem ruff/pytest necessário). Resuma em português com a tabela antes/depois.
