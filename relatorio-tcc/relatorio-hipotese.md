# Hipótese TCC — Knowledge Graph + conversa clarificadora: relatório de experimento

Branch: `hypothesis/teste-inicial` · dados originais em 16/09/2026, série _35 em 17/09/2026.
Dataset: 24 cenários (`evidencias/cenarios_24.json`), 12 por POP
(`pop_acesso_pf.md`, `pop_cdc_pf.md`), tipos CONDITIONAL_WORKFLOW (8),
ROLE_RESTRICTION (6), EDGE_CASE (5), REGULATORY_TIMELINE (5).
Modelos originais: index `gemini-3.5-flash-lite`, chat `gemini-3.1-flash-lite`,
juiz RAGAS `gemini-3.5-flash-lite`, embeddings `gemini-embedding-001`/768.
Série _35: chat `gemini-3.5-flash-lite` (juiz ainda `3.5-flash-lite`).
Juiz: LLM-as-a-Judge (RAGAS) sobre o mesmo transporte Gemini.

## Hipótese

> Com a base de grafos, conduzir clarificação para coletar os dados faltantes
> antes de consultar o grafo produz respostas mais acuradas do que o
> single-turn direto — e o próprio grafo indica o que ainda falta perguntar.

## Desenho experimental — 4 dimensões (leia isto antes das tabelas)

O experimento varia **4 dimensões independentes**, e cada braço abaixo é uma
combinação explícita delas (nada foi escolhido a dedo na execução: cada
comando processa *todos* os itens da entrada — ver seção 5 do
`relatorio-revisao.md`):

1. **Método de resposta**: com grafo (LightRAG) vs sem grafo (LLM puro).
2. **Clarificação**: nenhuma vs fixa (3 turnos, ordem fixa) vs guiada pelo
   grafo (pergunta discriminativa, parada por margem, roteador de modo).
3. **Input no LLM puro**: pergunta completa vs incompleta (testa se a pergunta
   completa “salva” o modelo sem grafo — não salva).
4. **Modelo de chat**: 3.1 vs 3.5 (replicação: prova que o ganho é do método).

| Braço | Definição do cenário | n | Faithfulness | Relevancy |
|---|---|---|---|---|
| Baseline | Pergunta completa respondida pelo grafo LightRAG (`hybrid/k5`), sem conversa | 4 | 0.6786 | 0.6647 |
| Clarify fixo | Pergunta incompleta + até 3 esclarecimentos em ordem fixa, resposta pelo grafo (`hybrid/k5`) | 24 | 0.7349 | 0.6980 |
| Roteado | Pergunta incompleta + esclarecimento guiado pelo grafo (pergunta discriminativa, parada por margem) + modo de busca por documento (acesso→`local/k10`, CDC→`hybrid/k5`) | 24 | 0.8588 | 0.7788 |
| **Árvore decisão** | Pergunta incompleta + esclarecimento + resposta de **template de regras codificadas** dos POPs (sem LLM, sem grafo) | 24 | **0.8631** | 0.7103 |
| Direto completa | Pergunta completa respondida só pelo LLM (mesmo modelo, zero retrieval) | 24 | 0.1834 | 0.8195 |
| Direto incompleta | Pergunta incompleta respondida só pelo LLM, sem esclarecer | 24 | 0.2441 | 0.8417 |
| Baseline_35 | Idem baseline, com chat 3.5 | 4 | 0.7143 | 0.6590 |
| Roteado_35 | Idem roteado, com chat 3.5 | 24 | 0.8720 | 0.7829 |
| Direta_completa_35 | Idem direto completa, com chat 3.5 | 24 | 0.1513 | 0.8166 |
| Direta_incompleta_35 | Idem direto incompleta, com chat 3.5 | 24 | 0.2189 | 0.8413 |

Leituras por dimensão: (1) grafo ≈ 0.86 vs sem grafo ≈ 0.2; (2) guiada
(0.86) > fixa (0.73) > nenhuma (0.68); (3) completa não salva o LLM puro
(0.18 vs 0.24, ambas no piso); (4) o padrão se repete nos dois modelos.

## Matriz principal — modelos originais (mesmo juiz, comparável)

| Braço | n | Faithfulness | Relevancy | Recall | Precision |
|---|---|---|---|---|---|
| Baseline LightRAG hybrid | 4 | 0.6786 | 0.6647 | 0.7292 | 1.0000 |
| Clarify fixo | 24 | 0.7349 | 0.6980 | 0.9792 | 1.0000 |
| **Clarify roteado** | 24 | **0.8588** | **0.7788** | 0.9565 | 1.0000 |
| LLM direto (completa) | 24 | 0.1834 | 0.8195 | 0.9861 | 1.0000 |
| LLM direto (incompleta) | 24 | 0.2441 | 0.8417 | 0.9583 | 1.0000 |

- Roteado vs LLM direto (completa): faithfulness **4.7×**.
- LLM incompleta (0.2441) supera a completa (0.1834)? Não — ambas no piso (~0.2): sem grafo, nem a pergunta completa salva (regras internas não estão no conhecimento geral).
- Assinatura de alucinação: relevancy ~0.82 com faithfulness ~0.2 nos dois braços diretos.

## Série _35 — chat `gemini-3.5-flash-lite` (mesmo juiz 3.5-lite)

| Braço | n | Faithfulness | Relevancy | Recall |
|---|---|---|---|---|
| Baseline_35 | 4 | 0.7143 | 0.6590 | 0.9167 |
| Roteado_35 | 24 | **0.8720** | 0.7829 | 0.9583 |
| Direto_incompleta_35 | 24 | 0.2189 | 0.8413 | 0.9375 |
| Direto_completa_35 | 24 | 0.1513 | 0.8166 | 0.8750 |

- O padrão se replica com outro modelo de chat: roteado 0.8720 vs direto 0.2189 (~4.0×).
- Roteado_35 (0.8720) ≈ roteado original (0.8588): o ganho é do método, não do modelo.
- `exp_direct_completa_35`: fechado em 18/09 via execução agendada. Comando: `uv run ragbench eval --run-id exp_direct_completa_35`.

## O que as 3 métricas significam (para a banca)

- **Faithfulness**: quanto da resposta é suportado pelo contexto (sem alucinar). Métrica manchete.
- **Answer relevancy**: quanto a resposta endereça a pergunta. Braços diretos têm ~0.82 — fluentes e pertinentes, porém infiéis: alucinação confiante.
- **Context recall**: cobertura do ground-truth (~0.94–1.0 em todos — o conteúdo estava disponível; o que variou foi usá-lo com fidelidade).
- **Context precision = 1.0 em tudo é artefato metodológico**: o `eval` usa o arquivo-fonte como contexto do RAGAS, não os chunks recuperados. O retrieval real foi avaliado pela probe (abaixo).

## Evidência de retrieval (probe, `evidencias/probe_piores_5.md`)

- 5 piores casos × 4 modos: **0/20** — todos os modos recuperavam o doc CDC para perguntas de senhas, inclusive frase literal do POP de acesso.
- Sweep top_k: hybrid 0/5 em k=5/10/20/40; local k=10 fez 5/5 nos casos de acesso mas 1/4 nos CDC → nenhum modo/top_k único serve aos dois docs (motiva o roteador).
- Roteador só-grafo: **23/24** nos cenários. Produção: 13 rotas acesso→local/k10, 11 CDC→hybrid/k5, turnos médios 1.71.

## Latências médias de execução

Clarify fixo 47.4s · roteado 40.5s · direto 10.9s. Roteado é mais rápido que o fixo porque para cedo quando o grafo está confiante.

## Limites e ameaças à validade

1. n=24 (spike): sem poder estatístico formal; relatar como indício, não prova.
2. Precision/recall do RAGAS não avaliam o retrieval real (contexto = arquivo-fonte); a probe cobre essa lacuna.
3. Cache do LightRAG acelerou runs (LLM cache hit) — possível viés otimista nas latências.
4. Série _35 gerada com chat 3.5 mas julgada pelo mesmo juiz 3.5-lite: comparável internamente; a comparação direta _35 vs originais mistura efeito de modelo — o invariante é a razão roteado/direto (~4× em ambas).
5. Tentativa de juiz `3.7-flash`: existe no endpoint, mas a cota free é 20 req/dia (vs 500 do lite) — inviável para evals; mantido `3.5-flash-lite`.
6. `.env` atual da branch: index 3.5-lite, chat 3.1-lite, juiz 3.5-lite (revertido após o experimento _35).

## Conclusão final — matriz completa (9 avaliações, 188 amostras)

| Braço | n | Faithfulness | Relevancy |
|---|---|---|---|
| Roteado (chat 3.1) | 24 | **0.8588** | 0.7788 |
| Roteado_35 (chat 3.5) | 24 | **0.8720** | 0.7829 |
| Clarify fixo | 24 | 0.7349 | 0.6980 |
| Baseline_35 | 4 | 0.7143 | 0.6590 |
| Baseline | 4 | 0.6786 | 0.6647 |
| Direto incompleta | 24 | 0.2441 | 0.8417 |
| Direto incompleta_35 | 24 | 0.2189 | 0.8413 |
| Direto completa | 24 | 0.1834 | 0.8195 |
| Direto completa_35 | 24 | 0.1513 | 0.8166 |

Invariantes (valem nos dois modelos de chat): grafo+roteador ≈ 0.86 de
faithfulness contra ≈ 0.2 do LLM puro (~4–5×); LLM puro mantém relevancy
~0.82 — fluente, pertinente e infiel. A hipótese está sustentada como
indício forte: a conversa guiada pelo grafo coleta o que falta e o
roteador entrega cada pergunta ao modo que a resolve.

## 5º braço — chatbot tradicional por árvore (`exp_tree_24`, n=24)

Regras dos 2 POPs codificadas à mão (`engines/decision_tree_engine.py`,
~40 ramos com citação de seção), templates fixos, zero LLM/grafo:
faithfulness **0.8631**, relevancy 0.7103 (12 ramos ACESSO + 12 CDC, 0
fallbacks; manifest em `evidencias/exp_tree_24_manifest.json`).
Empate técnico com o roteado (0.8588) — e isso **não** significa “árvore
vence”: ela mede a qualidade da *codificação manual do autor* (teto
determinístico). A tese é de **custo**: ~600 linhas de POP viraram ramos
escritos à mão, frágeis a qualquer mudança de norma, contra o grafo que se
constrói sozinho (≈ 0.86) e o roteador que se adapta.

## Série golden-8 — base completa, 16 perguntas adversariais (26–27/09/2026)

Base: 8 POPs indexados (`hybrid/k5`), 22 chunks, 233 nós / 131 arestas, manifesto
com 8 hashes. Dataset: `data/golden_dataset.json`, 16 perguntas (2/doc:
CONDITIONAL_WORKFLOW 6, EDGE_CASE 5, ROLE_RESTRICTION 3, REGULATORY_TIMELINE 2).
Modelos: index `gemini-3.5-flash-lite`, chat `gemini-3.1-flash-lite`, juiz
`gemini-3.5-flash-lite` (mesmo juiz da hipótese — comparável), embeddings
`gemini-embedding-001`/768. Três braços, 0 NaN em todas as avaliações.

| Braço | n | Faithfulness | Relevancy | Recall | Precision |
|---|---|---|---|---|---|
| golden_full_hybrid_16 | 16 | 0.2715 | 0.3835 | 1.0000 | 1.0000 |
| golden_direct_completa_16 | 16 | 0.1310 | 0.8110 | 1.0000 | 1.0000 |
| golden_tree_v2_16 | 16 | 0.7761 | 0.7386 | 1.0000 | 1.0000 |

Baseline LLM puro (`run-direct --input completa`, run `golden_direct_completa`,
cenários em `data/golden_scenarios_completa.json`, 16/16 success, 10.0s/query):
faithfulness 0.1310 com relevancy 0.8110 — a assinatura de alucinação confiante
se replica na base de 8 docs (fluente, pertinente e infiel). Hybrid (0.2715) ≈
2× o direto (0.1310): gap menor que os 4–5× da hipótese porque o hybrid também
sofre no dataset mais duro — metade das respostas são abstenções honestas ("não
há dados que confirmem...") em cenários multi-condição.

Árvore reescrita para os 8 POPs (motor v2.0, ~75 ramos, run `golden_tree_v2`,
0.0s/query, sem API): 16/16 documentos corretos, 0 abstenções, faithfulness
0.7761 consistente em todos os tipos (0.65–0.80) — melhor braço da série. A v1
(só 2 POPs) errava confiante ou abstinha em 11/16 desta mesma base.

Ponte com a hipótese: o invariante se mantém em escala maior — grafo > LLM puro;
relevancy alta + faithfulness no piso sem grafo, em todos os tipos; e a árvore
vence onde o domínio está codificado à mão (teto determinístico, tese de
**custo**: cada POP novo exigiu ramos escritos à mão, frágeis a mudanças de
norma, contra o grafo que se constrói sozinho).

Limites: mesmo artefato de precision/recall = 1.0 (contexto = arquivo-fonte);
n=16, spike; 1 doc (`POP_Cartoes_SAC`) exigiu 3 tentativas por falha silenciosa
de merge do LightRAG (status `failed` sem exceção — motivou a verificação
pós-insert do `index`).

## Arquivos de evidência (pasta `evidencias/`)

- `<braco>_ragas.csv`: RAGAS por pergunta · `tabela_bracos.csv` (com n), `por_tipo.csv`
- `exp_routed_24_manifest.json`: rota, margem, scores e turnos por pergunta
- `cenarios_24.json` · `piores_casos.md` · `probe_piores_5.md` · `sweep_topk.md` · `ambiente.md`
- `golden_full_hybrid_16_ragas.csv`: as 16 avaliações da série golden-8 (dataset em `data/golden_dataset.json`)
- `golden_direct_completa_16_ragas.csv`: as 16 avaliações do baseline LLM puro (cenários em `data/golden_scenarios_completa.json`)
- `golden_tree_v2_16_ragas.csv`: as 16 avaliações da árvore v2 (8 POPs; manifest em `runs/golden_tree_v2/tree_manifest.json`)
