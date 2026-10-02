# TCC — Efeito do crescimento do corpus (2 → 8 POPs) nos braços RAG

Relatório comparativo entre três conjuntos do benchmark `ragbench` (LightRAG +
Ollama/Gemini, avaliação LLM-as-a-Judge via RAGAS, juiz `gemini-3.5-flash-lite` nos
três conjuntos, cf. `RAGAS__JUDGE_MODEL` no `.env`).

- **2 POPs** (16–18/09/2026): `pop_acesso_pf.md` (12 cenários) + `pop_cdc_pf.md`
  (12 cenários) = 24 cenários (`data/hypothesis_inicial_scenarios.json`).
- **8 POPs intermediário** (26–27/09/2026): aos 2 POPs somaram-se 6 POPs anonimizados
  (Limites, Cartões SAC, Fatura, INSS, Alfa Rende Fácil, Bloqueio Judicial), avaliados
  com **16 golden** (2 por POP, `golden-00`…`golden-15`, com `pergunta_incompleta ==
  pergunta_completa` e `slots_simulados` vazio).
- **8 POPs final** (estado atual): mesmos 8 POPs, avaliados com **96 golden**
  (`golden96-00`…`golden96-95`, 12 por POP, incompleta ≠ completa, com
  `slots_simulados` preenchidos; `data/golden_scenarios_completa.json`). Os braços
  `golden_clarify_fixo`, `golden_routed` e `golden_tree_v2` já foram re-executados sobre
  os 96; `golden_full_hybrid` e `golden_direct_completa` ainda refletem o conjunto
  intermediário de 16 e estão pendentes de re-run nos 96.

![Comparativo RAGAS 2 vs 8 POPs](comparacao_2_vs_8_pops.png)

## Matriz comparativa — 4 métricas RAGAS por braço e conjunto

Fonte: `runs/<id>/resumo_qualidade_ragas.md` (métricas globais, conferidas contra a média
das colunas de `ragas_evaluation_results.csv`); `n` e latência média de
`runs/<id>/benchmark_analise_detalhada.csv` via `csv.DictReader`
(coluna `total_latency_seconds`). Os números do nível intermediário foram recuperados
dos arquivos de evidência versionados em git (runs não são versionados). Tabela
legível por máquina em `evidencias/tabela_bracos_2_vs_8.csv` (coluna `conjunto`:
`2pops-24`, `8pops-16`, `8pops-96`).

### Nível 1 — 2 POPs (24 cenários, exceto hybrid com n=4)

| Braço | Run | n | Faithfulness | Answer Relevancy | Context Recall | Context Precision | Lat. média |
|---|---|---|---|---|---|---|---|
| Grafo `hybrid/k5`, pergunta completa | `exp_baseline_hypothesis` | 4 | 0.6786 | 0.6647 | 0.7292 | 1.0000 | 1.7s |
| Incompleta + clarify fixo (≤3 turnos) + grafo `hybrid/k5` | `exp_clarify_24` | 24 | 0.7349 | 0.6980 | 0.9792 | 1.0000 | 47.4s |
| Incompleta + clarify guiado + rota por documento | `exp_routed_24` | 24 | 0.8588 | 0.7788 | 0.9565 | 1.0000 | 40.5s |
| Só LLM, pergunta completa (zero retrieval) | `exp_direct_completa` | 24 | 0.1834 | 0.8195 | 0.9861 | 1.0000 | 10.9s |
| Árvore de decisão (regras fixas, sem LLM/grafo) | `exp_tree_24` | 24 | 0.8631 | 0.7103 | 1.0000 | 1.0000 | 0.0s |

### Nível 2 — 8 POPs intermediário (16 golden, 2 por POP)

| Braço | Run | n | Faithfulness | Answer Relevancy | Context Recall | Context Precision | Lat. média |
|---|---|---|---|---|---|---|---|
| Grafo `hybrid/k5`, pergunta completa | `golden_full_hybrid` | 16 | 0.2715 | 0.3835 | 1.0000 | 1.0000 | 65.6s |
| Incompleta + clarify fixo (≤3 turnos) + grafo `hybrid/k5` | `golden_clarify_fixo` | 16 | 0.3522 | 0.4342 | 1.0000 | 1.0000 | 4.8s* |
| Incompleta + clarify guiado + rota por documento | `golden_routed` | 16 | 0.4783 | 0.5862 | 1.0000 | 1.0000 | 0.9s* |
| Só LLM, pergunta completa (zero retrieval) | `golden_direct_completa` | 16 | 0.1310 | 0.8110 | 1.0000 | 1.0000 | 10.0s |
| Árvore de decisão v2 (regras dos 8 POPs) | `golden_tree_v2` | 16 | 0.7761 | 0.7386 | 1.0000 | 1.0000 | 0.0s |

\* Latências achatadas por cache-hit de LLM nesses runs (ver ameaças à validade).

### Nível 3 — 8 POPs final (96 golden, 12 por POP)

| Braço | Run | n | Faithfulness | Answer Relevancy | Context Recall | Context Precision | Lat. média |
|---|---|---|---|---|---|---|---|
| Incompleta + clarify fixo (≤3 turnos) + grafo `hybrid/k5` | `golden_clarify_fixo` | 96 | 0.4731 | 0.5844 | 0.9649 | 1.0000 | 24.2s |
| Incompleta + clarify guiado + rota por documento | `golden_routed` | 96 | 0.5439 | 0.6579 | 0.9740 | 0.9896 | 5.1s |
| Árvore de decisão v2 (regras dos 8 POPs) | `golden_tree_v2` | 96 | 0.7362 | 0.6797 | 0.9722 | 0.9792 | 0.0s |

(Hybrid puro e só-LLM ainda sem re-run nos 96; valem os números do nível 2.)

Resumo da trajetória (faithfulness / relevancy): hybrid 0.68→0.27 (sem nível 3);
clarify_fixo 0.73→0.35→0.47 / 0.70→0.43→0.58; routed 0.86→0.48→0.54 /
0.78→0.59→0.66; direct 0.18→0.13 / 0.82→0.81; tree 0.86→0.78→0.74 /
0.71→0.74→0.68.

## O que aconteceu com o crescimento de 2 → 8 POPs

1. **O grafo puro colapsou.** Faithfulness do `hybrid/k5` caiu de 0.68 para 0.27
   (−60%) e relevancy de 0.66 para 0.38 (−42%) já no intermediário. Com 8 POPs,
   entidades e chunks de domínios distintos (CDC, acesso, cartões, INSS, judicial…)
   passam a competir no mesmo espaço vetorial: o retrieval retorna contexto do POP
   errado ou diluído, e o gerador ancora a resposta em fatos vizinhos incorretos. A
   latência média do braço (65.6s) é consistente com buscas mais ambíguas. Ressalvas:
   o baseline da era 2 POPs tem n=4 e o braço ainda não foi re-executado nos 96.
2. **O roteamento por documento mitigou, mas não salvou.** O braço roteado caiu de
   0.86 para 0.48 no intermediário (−44%) e recuperou para 0.54 nos 96 — perda menor
   que a do hybrid puro, porque restringir o modo de busca por documento reduz o
   vazamento entre POPs (no run atual: 62 consultas `hybrid/k5` + 34 `local/k10`).
   Continua sendo o melhor braço com grafo nos 8 POPs.
3. **Do intermediário para o final, o clarify passou a funcionar de verdade.** Nos 16
   golden, `incompleta == completa` e slots vazios implicavam 0 turnos de clarificação;
   nos 96, os slots vêm preenchidos e o clarify executa de fato (média 1.44 turnos no
   fixo e 1.24 no roteado) — o que explica a recuperação de faithfulness do fixo
   (0.35→0.47, +34%) e do roteado (0.48→0.54, +14%), com recall/precision saindo da
   saturação artificial em 1.0000 para 0.96–0.99.
4. **A árvore de regras foi a mais resistente ao crescimento.** Faithfulness 0.86 →
   0.78 → 0.74 (quedas de ~10% e ~5%, em parte variação entre questionários), porque
   resposta por template não depende de retrieval: cada novo POP vira um ramo
   determinístico novo, sem interferir nos existentes. O custo aparece em outro lugar:
   manutenção manual das regras (árvore v2 precisou de ramos para os 8 POPs +
   detecção anti-colisão).
5. **O só-LLM é o piso da comparação e não mudou** (faithfulness 0.18 → 0.13, sempre
   baixo; relevancy 0.82 → 0.81, estável): sem grounding, o modelo responde bem na
   forma e erra no conteúdo, independente do tamanho do corpus.
6. **Recall/precision perto do teto; a degradação concentra-se em faithfulness e
   relevancy.** No intermediário, recall e precision saturaram em 1.0000; nos 96,
   ficam em 0.96–1.00: o contexto recuperado ainda *contém* a resposta na maioria dos
   casos, mas o gerador ancora-se nos trechos errados do contexto maior e mais ruidoso.

## Experimento de tuning revertido (27/09, sobre o conjunto de 16 golden)

Na tentativa de recuperar o braço roteado testou-se, sobre as 16 golden: `local/k10 →
k5` no acesso, remoção da anotação `[Dados coletados…]` da query de retrieval e prompt
sistêmico de compliance mais rígido. Resultado: faithfulness 0.4783 → ~0.25, relevancy
0.5862 → ~0.33. As alterações foram **revertidas** (a configuração atual confirma o
revert: `golden_routed` usa `local/k10` no acesso e `hybrid/k5` nos demais, com a
anotação de dados coletados presente nas queries enriquecidas). Lição: menos contexto
(k5) cortou evidência necessária em vez de ruído, e o prompt mais duro mudou o estilo
das respostas de forma penalizada pelo juiz. Os números do roteado nos 96 golden
(0.5439 / 0.6579) já refletem a configuração revertida.

## Ameaças à validade

- Conjuntos de perguntas diferentes entre os três níveis (24 cenários situacionais vs
  16 golden adversariais vs 96 `golden96-*`, 12 por POP) e N assimétrico no baseline
  hybrid (n=4) — o efeito-corpus está confundido com o efeito-questionário.
- `golden_full_hybrid` e `golden_direct_completa` ainda refletem só o intermediário
  (n=16), pendentes de re-run nos 96.
- No intermediário, `pergunta_incompleta == pergunta_completa` e `slots_simulados`
  vazio: os braços de clarificação executaram 0 turnos — o contraste com/sem
  esclarecimento está subestimado no nível 2. O nível 3 corrige isso (slots
  preenchidos; clarify médio 1.44 turnos no fixo e 1.24 no roteado).
- Cache-hit de LLM nos runs intermediários achata as latências dos braços de grafo
  (4.8s/0.9s); os re-runs nos 96 registram 0.0% de cache-hit
  (`resumo_benchmark.md`), com latências genuínas (24.2s/5.1s).
- Juiz único (`gemini-3.5-flash-lite`); variação entre rodadas do juiz explica
  oscilações de ~±0.05.

## Evidências (pasta `evidencias/`)

- `era2_*_ragas.csv` (5 arquivos): resultados RAGAS por amostra da era 2 POPs (de
  `runs/exp_*/ragas_evaluation_results.csv`).
- `era8_16_clarify_fixo_ragas.csv`, `era8_16_routed_ragas.csv`,
  `era8_16_tree_ragas.csv`: resultados RAGAS por amostra do intermediário (n=16,
  recuperados do git — os runs foram re-executados e não são versionados); o
  intermediário de hybrid/direct coincide com `era8_hybrid_ragas.csv` /
  `era8_direct_ragas.csv` (ainda nos 16).
- `era8_*_ragas.csv` (5 arquivos): resultados RAGAS por amostra do estado atual (de
  `runs/golden_*/ragas_evaluation_results.csv`; n=16 em hybrid/direct, n=96 nos
  demais).
- `era2_*_manifest.json` (clarify_fixo, routed, direct, tree),
  `era8_16_*_manifest.json` (clarify_fixo, routed, tree),
  `era8_*_manifest.json` (clarify_fixo, routed, direct, tree): manifests de
  clarify/tree/direct dos runs (braços hybrid puros não possuem manifest).
- `cenarios_2pops.json` (24 cenários, de `data/hypothesis_inicial_scenarios.json`),
  `cenarios_8pops_16.json` (16 golden intermediárias, `golden-00`…`golden-15`) e
  `cenarios_8pops.json` (96 golden finais, de `data/golden_scenarios_completa.json`).
- `tabela_bracos_2_vs_8.csv`: tabela-fonte da matriz acima, legível por máquina
  (`conjunto,pops,braco,run,n,faithfulness,answer_relevancy,context_recall,context_precision,lat_media_s`).
