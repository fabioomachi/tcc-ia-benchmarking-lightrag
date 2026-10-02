# TCC — Efeito do crescimento do corpus (2 → 8 POPs) nos braços RAG

Relatório comparativo entre duas eras do benchmark `ragbench` (LightRAG + Ollama/Gemini,
avaliação LLM-as-a-Judge via RAGAS, juiz `gemini-3.5-flash-lite` em ambas as eras,
cf. `RAGAS__JUDGE_MODEL` no `.env`).

- **Era 2 POPs** (16–18/09/2026): `pop_acesso_pf.md` (12 cenários) + `pop_cdc_pf.md`
  (12 cenários) = 24 cenários (`data/hypothesis_inicial_scenarios.json`).
- **Era 8 POPs**: aos 2 POPs somaram-se 6 POPs anonimizados (Limites, Cartões SAC,
  Fatura, INSS, Alfa Rende Fácil, Bloqueio Judicial). O arquivo de cenários da era
  (`data/golden_scenarios_completa.json`, estado atual da árvore de trabalho) contém
  **96 cenários golden** (`golden96-00`…`golden96-95`, 12 por POP, incompleta ≠ completa,
  com `slots_simulados` preenchidos). Os braços `golden_clarify_fixo`, `golden_routed` e
  `golden_tree_v2` já foram re-executados sobre esses 96 cenários; `golden_full_hybrid` e
  `golden_direct_completa` ainda refletem o conjunto antigo de **16 golden** (2 por POP,
  `HEAD:data/golden_scenarios_completa.json`, com `pergunta_incompleta == pergunta_completa`
  e `slots_simulados` vazio) e estão pendentes de re-run nos 96.

![Comparativo RAGAS 2 vs 8 POPs](comparacao_2_vs_8_pops.png)

## Matriz comparativa — 4 métricas RAGAS por braço e era

Fonte: `runs/<id>/resumo_qualidade_ragas.md` (métricas globais, conferidas contra a média
das colunas de `ragas_evaluation_results.csv`); `n` e latência média de
`runs/<id>/benchmark_analise_detalhada.csv` via `csv.DictReader`
(coluna `total_latency_seconds`). Tabela legível por máquina em
`evidencias/tabela_bracos_2_vs_8.csv`.

### Nível 1 — 2 POPs (24 cenários, exceto hybrid com n=4)

| Braço | Run | n | Faithfulness | Answer Relevancy | Context Recall | Context Precision | Lat. média |
|---|---|---|---|---|---|---|---|
| Grafo `hybrid/k5`, pergunta completa | `exp_baseline_hypothesis` | 4 | 0.6786 | 0.6647 | 0.7292 | 1.0000 | 1.7s |
| Incompleta + clarify fixo (≤3 turnos) + grafo `hybrid/k5` | `exp_clarify_24` | 24 | 0.7349 | 0.6980 | 0.9792 | 1.0000 | 47.4s |
| Incompleta + clarify guiado + rota por documento | `exp_routed_24` | 24 | 0.8588 | 0.7788 | 0.9565 | 1.0000 | 40.5s |
| Só LLM, pergunta completa (zero retrieval) | `exp_direct_completa` | 24 | 0.1834 | 0.8195 | 0.9861 | 1.0000 | 10.9s |
| Árvore de decisão (regras fixas, sem LLM/grafo) | `exp_tree_24` | 24 | 0.8631 | 0.7103 | 1.0000 | 1.0000 | 0.0s |

### Nível 2 — 8 POPs (n=16 no conjunto antigo, n=96 no conjunto atual de 96 golden)

| Braço | Run | n | Faithfulness | Answer Relevancy | Context Recall | Context Precision | Lat. média |
|---|---|---|---|---|---|---|---|
| Grafo `hybrid/k5`, pergunta completa | `golden_full_hybrid` | 16 | 0.2715 | 0.3835 | 1.0000 | 1.0000 | 65.6s |
| Incompleta + clarify fixo (≤3 turnos) + grafo `hybrid/k5` | `golden_clarify_fixo` | 96 | 0.4731 | 0.5844 | 0.9649 | 1.0000 | 24.2s |
| Incompleta + clarify guiado + rota por documento | `golden_routed` | 96 | 0.5439 | 0.6579 | 0.9740 | 0.9896 | 5.1s |
| Só LLM, pergunta completa (zero retrieval) | `golden_direct_completa` | 16 | 0.1310 | 0.8110 | 1.0000 | 1.0000 | 10.0s |
| Árvore de decisão v2 (regras dos 8 POPs) | `golden_tree_v2` | 96 | 0.7362 | 0.6797 | 0.9722 | 0.9792 | 0.0s |

Resumo antes/depois (faithfulness / relevancy): hybrid 0.68→0.27 / 0.66→0.38;
clarify_fixo 0.73→0.47 / 0.70→0.58; routed 0.86→0.54 / 0.78→0.66;
direct 0.18→0.13 / 0.82→0.81; tree 0.86→0.74 / 0.71→0.68.

## O que aconteceu com o crescimento de 2 → 8 POPs

1. **O grafo puro colapsou.** Faithfulness do `hybrid/k5` caiu de 0.68 para 0.27
   (−60%) e relevancy de 0.66 para 0.38 (−42%). Com 8 POPs, entidades e chunks de
   domínios distintos (CDC, acesso, cartões, INSS, judicial…) passam a competir no
   mesmo espaço vetorial: o retrieval retorna contexto do POP errado ou diluído, e o
   gerador ancora a resposta em fatos vizinhos incorretos. A latência média do braço
   (65.6s no conjunto de 16) é consistente com buscas mais ambíguas. Ressalva: o
   baseline da era 2 POPs tem n=4 e o braço ainda não foi re-executado nos 96 golden.
2. **O roteamento por documento mitigou, mas não salvou.** O braço roteado caiu de
   0.86 para 0.54 de faithfulness (−37%) e de 0.78 para 0.66 de relevancy — perda
   menor que a do hybrid puro, porque restringir o modo de busca por documento reduz
   o vazamento entre POPs (no run atual: 62 consultas `hybrid/k5` + 34 `local/k10`).
   Continua sendo o melhor braço com grafo na era 8 POPs, e o clarify guiado agora
   executa turnos reais (média 1.24 turnos nas 96 golden, vs 0 turnos no conjunto
   antigo de 16).
3. **A árvore de regras foi a mais resistente ao crescimento.** Faithfulness 0.86 →
   0.74 (−15%) e relevancy 0.71 → 0.68 (−4%), porque resposta por template não depende
   de retrieval: cada novo POP vira um ramo determinístico novo, sem interferir nos
   existentes. O custo aparece em outro lugar: manutenção manual das regras (árvore v2
   precisou de ramos para os 8 POPs + detecção anti-colisão).
4. **O só-LLM é o piso da comparação e não mudou** (faithfulness 0.18 → 0.13, sempre
   baixo; relevancy 0.82 → 0.81, estável): sem grounding, o modelo responde bem na
   forma e erra no conteúdo, independente do tamanho do corpus.
5. **Recall/precision perto do teto, degradação concentrada em faithfulness/relevancy.**
   No conjunto antigo de 16 golden, recall e precision saturaram em 1.0000; no
   conjunto atual de 96, ficam em 0.96–1.00 (clarify/routed/tree): o contexto
   recuperado ainda *contém* a resposta na maioria dos casos, mas o gerador ancora-se
   nos trechos errados do contexto maior e mais ruidoso — por isso a queda aparece em
   faithfulness e relevancy.

## Experimento de tuning revertido (27/09, sobre o conjunto de 16 golden)

Na tentativa de recuperar o braço roteado testou-se, sobre as 16 golden antigas:
`local/k10 → k5` no acesso, remoção da anotação `[Dados coletados…]` da query de
retrieval e prompt sistêmico de compliance mais rígido. Resultado: faithfulness
0.4783 → ~0.25, relevancy 0.5862 → ~0.33. As alterações foram **revertidas** (a
configuração atual confirma o revert: `golden_routed` usa `local/k10` no acesso e
`hybrid/k5` nos demais, com a anotação de dados coletados presente nas queries
enriquecidas). Lição: menos contexto (k5) cortou evidência necessária em vez de
ruído, e o prompt mais duro mudou o estilo das respostas de forma penalizada pelo
juiz. Os números atuais do roteado nos 96 golden (0.5439 / 0.6579) já refletem a
configuração revertida.

## Ameaças à validade

- Conjuntos de perguntas diferentes entre eras e dentro da era 8 POPs: 24 cenários
  situacionais (era 2) vs 16 golden adversariais antigas (hybrid/direct) vs 96 golden
  `golden96-*` (clarify/routed/tree, 12 por POP) — o efeito-corpus está confundido com
  o efeito-questionário.
- N assimétrico: baseline hybrid n=4; na era 8, hybrid/direct n=16 vs demais n=96.
  `golden_full_hybrid` e `golden_direct_completa` pendentes de re-run nos 96 cenários.
- No conjunto antigo de 16 golden, `pergunta_incompleta == pergunta_completa` e
  `slots_simulados` vazio: os braços de clarificação executaram 0 turnos — o
  contraste com/sem esclarecimento está subestimado nesses dois runs. O conjunto de
  96 corrige isso (slots preenchidos; clarify médio 1.44 turnos no fixo e 1.24 no
  roteado).
- Latências: todos os `resumo_benchmark.md` atuais registram 0.0% de cache-hit, de
  modo que as médias (ex.: routed 5.1s nos 96 vs 40.5s nos 24) refletem tamanho das
  perguntas/caminhos de retrieval, não devendo ser comparadas como medida pura de
  custo do corpus.
- Juiz único (`gemini-3.5-flash-lite`); variação entre rodadas do juiz explica
  oscilações de ~±0.05.

## Evidências (pasta `evidencias/`)

- `era2_hybrid_ragas.csv`, `era2_clarify_fixo_ragas.csv`, `era2_routed_ragas.csv`,
  `era2_direct_ragas.csv`, `era2_tree_ragas.csv`: resultados RAGAS por amostra da era
  2 POPs (de `runs/exp_*/ragas_evaluation_results.csv`).
- `era8_hybrid_ragas.csv`, `era8_clarify_fixo_ragas.csv`, `era8_routed_ragas.csv`,
  `era8_direct_ragas.csv`, `era8_tree_ragas.csv`: resultados RAGAS por amostra da era
  8 POPs (de `runs/golden_*/ragas_evaluation_results.csv`; n=16 em hybrid/direct,
  n=96 nos demais).
- `era2_clarify_fixo_manifest.json`, `era2_routed_manifest.json`,
  `era2_direct_manifest.json`, `era2_tree_manifest.json`,
  `era8_clarify_fixo_manifest.json`, `era8_routed_manifest.json`,
  `era8_direct_manifest.json`, `era8_tree_manifest.json`: manifests de
  clarify/tree/direct dos runs (braços hybrid puros não possuem manifest).
- `cenarios_2pops.json` (24 cenários, era 2 POPs, de
  `data/hypothesis_inicial_scenarios.json`) e `cenarios_8pops.json` (96 cenários,
  era 8 POPs, de `data/golden_scenarios_completa.json` no estado atual da árvore).
- `tabela_bracos_2_vs_8.csv`: tabela-fonte da matriz acima, legível por máquina
  (`pops,braco,run,n,faithfulness,answer_relevancy,context_recall,context_precision,lat_media_s`).
