# TCC — Efeito do crescimento do corpus (2 → 8 POPs) nos braços RAG

Relatório comparativo entre duas eras do benchmark `ragbench` (LightRAG + Ollama/Gemini,
avaliação LLM-as-a-Judge via RAGAS, juiz `gemini-3.5-flash-lite` em ambas as eras).

- **Era 2 POPs** (16–18/09/2026): `pop_acesso_pf.md` (12 cenários) + `pop_cdc_pf.md`
  (12 cenários) = 24 cenários (`data/hypothesis_inicial_scenarios.json`).
- **Era 8 POPs** (26–27/09/2026): 6 POPs anonimizados adicionados (Limites, Cartões SAC,
  Fatura, INSS, Alfa Rende Fácil, Bloqueio Judicial) = 16 perguntas golden adversariais,
  2 por POP (`data/golden_scenarios_completa.json`).

![Comparativo RAGAS 2 vs 8 POPs](comparacao_2_vs_8_pops.png)

## Matriz comparativa — 4 métricas RAGAS por braço e era

### Nível 1 — 2 POPs (24 cenários, exceto hybrid)

| Braço | Run | n | Faithfulness | Answer Relevancy | Context Recall | Context Precision | Lat. média |
|---|---|---|---|---|---|---|---|
| Grafo `hybrid/k5`, pergunta completa | `exp_baseline_hypothesis` | 4 | 0.6786 | 0.6647 | 0.7292 | 1.0000 | 1.7s |
| Incompleta + clarify fixo (≤3 turnos) + grafo `hybrid/k5` | `exp_clarify_24` | 24 | 0.7349 | 0.6980 | 0.9792 | 1.0000 | 47.4s |
| Incompleta + clarify guiado + rota por doc | `exp_routed_24` | 24 | 0.8588 | 0.7788 | 0.9565 | 1.0000 | 40.5s |
| Só LLM, pergunta completa (zero retrieval) | `exp_direct_completa` | 24 | 0.1834 | 0.8195 | 0.9861 | 1.0000 | 10.9s |
| Árvore de decisão (regras fixas, sem LLM/grafo) | `exp_tree_24` | 24 | 0.8631 | 0.7103 | 1.0000 | 1.0000 | 0.0s |

### Nível 1 — 8 POPs (16 golden)

| Braço | Run | n | Faithfulness | Answer Relevancy | Context Recall | Context Precision | Lat. média |
|---|---|---|---|---|---|---|---|
| Grafo `hybrid/k5`, pergunta completa | `golden_full_hybrid` | 16 | 0.2715 | 0.3835 | 1.0000 | 1.0000 | 65.6s |
| Incompleta + clarify fixo (≤3 turnos) + grafo `hybrid/k5` | `golden_clarify_fixo` | 16 | 0.3522 | 0.4342 | 1.0000 | 1.0000 | 4.8s* |
| Incompleta + clarify guiado + rota por doc (`local/k10` acesso, `hybrid/k5` CDC) | `golden_routed` | 16 | 0.4783 | 0.5862 | 1.0000 | 1.0000 | 0.9s* |
| Só LLM, pergunta completa (zero retrieval) | `golden_direct_completa` | 16 | 0.1310 | 0.8110 | 1.0000 | 1.0000 | 10.0s |
| Árvore de decisão v2 (regras dos 8 POPs) | `golden_tree_v2` | 16 | 0.7761 | 0.7386 | 1.0000 | 1.0000 | 0.0s |

\* Latências achatadas por cache-hit de LLM (ver ameaças à validade).

## O que aconteceu com o crescimento de 2 → 8 POPs

1. **O grafo puro colapsou.** Faithfulness do `hybrid/k5` caiu de 0.68 para 0.27
   (−60%) e relevancy de 0.66 para 0.38. Com 8 POPs, entidades e chunks de domínios
   distintos (CDC, acesso, cartões, INSS, judicial…) passam a competir no mesmo espaço
   vetorial: o retrieval retorna contexto do POP errado ou diluído, e o gerador ancora a
   resposta em fatos vizinhos incorretos. A latência média subiu (47s → 66s), consistente
   com buscas mais ambíguas.
2. **O roteamento por documento mitigou, mas não salvou.** O braço roteado caiu de 0.86
   para 0.48 de faithfulness — perda de 44%, menor que os 60% do hybrid puro, porque
   restringir o modo de busca por documento (`local` p/ acesso, `hybrid` p/ CDC) reduz o
   vazamento entre POPs. Continua sendo o melhor braço com grafo na era 8 POPs.
3. **A árvore de regras foi imune ao crescimento.** Faithfulness 0.86 → 0.78 (queda de
   ~10%, dentro da variação entre questionários), porque resposta por template não depende
   de retrieval: cada novo POP vira um ramo determinístico novo, sem interferir nos
   existentes. O custo aparece em outro lugar: manutenção manual das regras (árvore v2
   precisou de ramos para os 8 POPs + detecção anti-colisão).
4. **O só-LLM não mudou** (faithfulness 0.18 → 0.13, sempre baixo; relevancy ~0.81 estável):
   sem grounding, o modelo responde bem na forma e erra no conteúdo, independente do
   tamanho do corpus — é o piso da comparação.
5. **Recall/precision saturaram em 1.0 na era 8 POPs.** Toda a degradação observável
   concentrou-se em faithfulness e relevancy: o contexto recuperado ainda *contém* a
   resposta (recall alto), mas o gerador se ancora nos trechos errados do contexto maior
   e mais ruidoso.

## Experimento de tuning revertido (27/09)

Na tentativa de recuperar o braço roteado testou-se: `local/k10 → k5` no acesso, remoção
da anotação `[Dados coletados…]` da query de retrieval e prompt sistêmico de compliance
mais rígido. Resultado: faithfulness 0.47 → 0.25, relevancy 0.64 → 0.33. As alterações
foram **revertidas** e o re-run pós-revert confirmou a recuperação (0.4783 / 0.5862).
Lição: menos contexto (k5) cortou evidência necessária em vez de ruído, e o prompt mais
duro mudou o estilo das respostas de forma penalizada pelo juiz.

## Ameaças à validade

- Conjuntos de perguntas diferentes entre eras (24 cenários situacionais vs 16 golden
  adversariais) e N assimétrico no baseline hybrid (n=4 vs n=16).
- Nos cenários golden, `pergunta_incompleta == pergunta_completa` e `slots_simulados`
  vazio: os braços de clarificação executaram 0 turnos — o contraste com/sem
  esclarecimento está subestimado.
- Cache-hit de LLM nos runs golden achata as latências dos braços de grafo (4.8s/0.9s).
- Juiz único (`gemini-3.5-flash-lite`); variação entre rodadas do juiz explica oscilações
  de ~±0.05 (ex.: relevancy do roteado 0.64 → 0.59 no re-run).

## Evidências (pasta `evidencias/`)

- `*_ragas.csv`: resultados RAGAS por amostra dos 10 runs (5 braços × 2 eras).
- `*_manifest.json`: manifests de clarify/tree/direct dos runs golden + roteado 24.
- `hypothesis_inicial_scenarios.json` (24 cenários, era 2 POPs) e
  `golden_scenarios_completa.json` (16 cenários, era 8 POPs).
- `tabela_bracos_2_vs_8.csv`: tabela-fonte da matriz acima, legível por máquina.
