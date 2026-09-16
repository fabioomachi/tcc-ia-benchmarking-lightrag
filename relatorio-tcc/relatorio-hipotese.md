# Hipótese TCC — Knowledge Graph + conversa clarificadora: relatório de experimento

Branch: `hypothesis/teste-inicial` · commit `9bbe766` · dados gerados em 16/09/2026.
Dataset: 24 cenários (`evidencias/cenarios_24.json`), 12 por POP
(`pop_acesso_pf.md`, `pop_cdc_pf.md`), tipos CONDITIONAL_WORKFLOW (8),
ROLE_RESTRICTION (6), EDGE_CASE (5), REGULATORY_TIMELINE (5).
Modelos: index `gemini-3.5-flash-lite`, chat `gemini-3.1-flash-lite`,
juiz RAGAS `gemini-3.5-flash-lite`, embeddings `gemini-embedding-001`/768.
Juiz: LLM-as-a-Judge (RAGAS) sobre o mesmo transporte Gemini.

## Hipótese

> Com a base de grafos, conduzir clarificação para coletar os dados faltantes
> antes de consultar o grafo produz respostas mais acuradas do que o
> single-turn direto — e o próprio grafo indica o que ainda falta perguntar.

## Desenho (4 braços, n=24 salvo baseline)

| Braço | Run | O que faz |
|---|---|---|
| Baseline LightRAG | `exp_baseline_hypothesis` (n=4) | `run` hybrid/k5, perguntas completas |
| Clarify fixo | `exp_clarify_24` | `run-clarify` hybrid/k5, 3 turnos fixos |
| Clarify roteado | `exp_routed_24` | `run-clarify` + roteador só-grafo (acesso→local/k10, CDC→hybrid/k5), parada por margem |
| LLM direto | `exp_direct_completa` | `run-direct`, mesmo modelo, zero retrieval |

## Resultado principal (médias RAGAS)

| Braço | Faithfulness | Relevancy | Recall | Precision |
|---|---|---|---|---|
| Baseline (n=4) | 0.6786 | 0.6647 | 0.7292 | 1.0000 |
| Clarify fixo (n=24) | 0.7349 | 0.6980 | 0.9792 | 1.0000 |
| **Clarify roteado (n=24)** | **0.8588** | **0.7788** | 0.9565 | 1.0000 |
| LLM direto (n=24) | 0.1834 | 0.8195 | 0.9861 | 1.0000 |

- Roteado vs fixo: faithfulness **+0.1239**, relevancy **+0.0808**.
- Roteado vs LLM direto: faithfulness **4.7×** (0.8588 vs 0.1834).
- Assinatura de alucinação no braço direto: relevancy 0.8195 (fluente) com faithfulness 0.1834 (sem ancoragem).

## Por tipo de pergunta (roteado vs fixo, faithfulness)

| Tipo | Fixo | Roteado |
|---|---|---|
| CONDITIONAL_WORKFLOW | 0.8049 | 0.9055 |
| ROLE_RESTRICTION | 0.8538 | 0.9404 |
| REGULATORY_TIMELINE | 0.7571 | 0.8992 |
| EDGE_CASE | 0.4578 | 0.6456 |

## O que as 3 métricas significam (para a banca)

- **Faithfulness**: quanto da resposta é suportado pelo contexto (sem alucinar). O juiz quebra a resposta em afirmações e checa cada uma. É a métrica manchete: 0.8588 (roteado) vs 0.1834 (LLM puro).
- **Answer relevancy**: quanto a resposta endereça a pergunta (perguntas geradas da resposta vs original). O braço direto tem 0.8195 — fluente e pertinente, porém infiel: alucinação confiante.
- **Context recall**: cobertura do ground-truth (~0.96–1.0 em todos os braços — o conteúdo estava disponível; o que variou foi usá-lo com fidelidade).
- **Context precision = 1.0 em tudo é artefato metodológico**: o `eval` usa o arquivo-fonte como contexto do RAGAS, não os chunks recuperados. O retrieval real foi avaliado pela probe (abaixo), não por esta métrica.

## Evidência de retrieval (probe, `evidencias/probe_piores_5.md`)

- 5 piores casos × 4 modos: **0/20** — todos os modos recuperavam o doc CDC para perguntas de senhas, inclusive frase literal do POP de acesso.
- Sweep top_k: hybrid 0/5 em k=5/10/20/40; local k=10 fez 5/5 nos casos de acesso mas 1/4 nos CDC → nenhum modo/top_k único serve aos dois docs (motiva o roteador).
- Roteador só-grafo (overlap ponderado com entidades do índice): **23/24** nos cenários, 6 paradas precoces por confiança.
- Produção (`exp_routed_24_manifest.json`): 13 rotas acesso→local/k10, 11 CDC→hybrid/k5 (1 erro: `cdc_fraude_correspondente`, margem 0.003 — o sistema sinalizou incerteza), turnos médios 1.71, 0 reparos necessários.

## Latências médias de execução

Clarify fixo 47.4s · roteado 40.5s · direto 10.9s · baseline 1.7s (cache). Roteado é mais rápido que o fixo porque para cedo quando o grafo está confiante.

## Limites e ameaças à validade

1. n=24 (spike): sem poder estatístico formal; relatar como indício, não prova.
2. Precision/recall do RAGAS não avaliam o retrieval real (contexto = arquivo-fonte); a probe cobre essa lacuna.
3. Cache do LightRAG acelerou runs (LLM cache hit) — possível viés otimista nas latências.
4. 4º braço (`exp_direct_incompleta`, run pronta) sem eval: cota free-tier Gemini (500 req/dia) esgotada após 2 tentativas de 60 min. Comando: `uv run ragbench eval --run-id exp_direct_incompleta`.
5. Extração de entidades do índice é genérica (`organization`/`artifact`), não a ontologia bancária — o roteador contorna o viés, não o cura.

## Arquivos de evidência (pasta `evidencias/`)

- `<braco>_ragas.csv`: RAGAS por pergunta (4 braços avaliados) · `tabela_bracos.csv`, `por_tipo.csv`: agregados
- `exp_routed_24_manifest.json`: rota, margem, scores e turnos por pergunta (auditoria)
- `cenarios_24.json`: dataset dos 24 cenários · `piores_casos.md`: 5 piores com Q/A/GT
- `probe_piores_5.md`: tabela 0/20 por modo · `sweep_topk.md`: comparativo top_k
- `ambiente.md`: modelos, commit, cotas e comandos de reprodução
