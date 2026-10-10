# Desenvolvimento e Execução do `ragbench` — Relatório para TCC

> **Documento complementar:** ver também [`timeline-projeto.md`](timeline-projeto.md) — timeline commit a commit de 06/09 a 05/10/2026 (57 commits) que sustenta a narrativa abaixo.
> **Resultado experimental:** ver [`relatorio-2-vs-8-pops.md`](relatorio-2-vs-8-pops.md) — matriz 3 níveis x 5 braços, gráfico e ameaças à validade.
> **Dados auditáveis:** pasta [`evidencias/`](evidencias/) + tabela-máquina [`evidencias/tabela_bracos_2_vs_8.csv`](evidencias/tabela_bracos_2_vs_8.csv).

Estado em 09/10/2026, branch `main` (série v2 com código em working tree, não
commitado; último commit `57813bb`). Repositório: `github.com/fabioomachi/tcc-ia-benchmarking-lightrag`.

## 1. Objeto e pergunta de pesquisa

O `ragbench` é um framework de benchmarking para arquiteturas RAG em domínio regulatório bancário, especializado em **Knowledge Graph RAG (LightRAG)** com avaliação **LLM-as-a-Judge via RAGAS**.

Pergunta conduzida no repositório:

> Com a base de grafos, conduzir clarificação para coletar os dados que faltam produz respostas mais acuradas do que o single-turn direto — e o próprio grafo indica o que ainda falta perguntar?

## 2. Desenho atual — 3 conjuntos x 5 braços

Ver detalhamento da evolução em [`timeline-projeto.md`](timeline-projeto.md) (Fases 4–5).

- **Nível 1 — 2 POPs (16–18/09/2026):** `pop_acesso_pf.md` (senhas/acesso) + `pop_cdc_pf.md` (crédito) = 24 cenários situacionais (`data/hypothesis_inicial_scenarios.json`, 12+12).
- **Nível 2 — 8 POPs intermediário (26–27/09/2026):** aos 2 POPs somam-se 6 POPs anonimizados (Limites, Cartões SAC, Fatura, INSS, Alfa Rende Fácil, Bloqueio Judicial), avaliados com **16 golden** (2 por POP, `golden-00`…`golden-15`, com `pergunta_incompleta == pergunta_completa` e `slots_simulados` vazio → clarify executa 0 turnos).
- **Nível 3 — 8 POPs final (02–05/10/2026):** mesmos 8 POPs, avaliados com **96 golden** (`golden96-00`…`golden96-95`, 12 por POP, incompleta ≠ completa, `slots_simulados` preenchidos; `data/golden_scenarios_completa.json`, 96 itens confirmados). Todos os 5 braços têm re-run nos 96 — hybrid e direct sob novos run-ids (`*_96`), preservando os runs de 16 como controle.

Braços (mesmos modelos, juiz único `gemini-3.5-flash-lite` nos 3 níveis):

| # | Braço | Comando | Retrieval |
|---|---|---|---|
| 1 | Grafo `hybrid/k5`, pergunta completa | `run --mode hybrid --top-k 5` | LightRAG hybrid |
| 2 | Incompleta + clarify fixo (≤3 turnos) + grafo | `run-clarify` | `hybrid/k5` |
| 3 | Incompleta + clarify guiado + rota por documento | `run-clarify` (roteador on/off via `ROUTING__ENABLED`) | legado: `local/k10` p/ acesso, `hybrid/k5` p/ demais (nos 96: 62 `hybrid/k5` + 34 `local/k10`); **v2 (N-POPs)**: estratégias via `RoutingSettings.strategies` + default `hybrid/k5`, scoring por recall sobre a query + bônus de keywords normativas |
| 4 | Só LLM, pergunta completa (zero retrieval) | `run-direct` | nenhum |
| 5 | Árvore de decisão, regras fixas (zero LLM/grafo) | `run-tree` | nenhum |

Métricas RAGAS: `faithfulness`, `answer_relevancy`, `context_recall`, `context_precision` + latência/TTFT.

Fonte dos números: `runs/<id>/resumo_qualidade_ragas.md` (métricas globais, conferidas contra a média de `ragas_evaluation_results.csv`); `n` e latência média de `runs/<id>/benchmark_analise_detalhada.csv` via `csv.DictReader` (coluna `total_latency_seconds`). Números do intermediário de clarify/routed/tree recuperados dos arquivos de evidência versionados em git (runs não são versionados).

## 3. Matriz atualizada (substitui qualquer versão 2x5)

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
| Grafo `hybrid/k5`, pergunta completa | `golden_full_hybrid_96` | 96 | 0.4050 | 0.5317 | 0.9896 | 0.9896 | 90.8s |
| Incompleta + clarify fixo (≤3 turnos) + grafo `hybrid/k5` | `golden_clarify_fixo` | 96 | 0.4731 | 0.5844 | 0.9649 | 1.0000 | 24.2s |
| Incompleta + clarify guiado + rota por documento | `golden_routed` | 96 | 0.5439 | 0.6579 | 0.9740 | 0.9896 | 5.1s |
| Só LLM, pergunta completa (zero retrieval) | `golden_direct_completa_96` | 96 | 0.1534 | 0.8016 | 0.9896 | 0.9896 | 16.3s |
| Árvore de decisão v2 (regras dos 8 POPs) | `golden_tree_v2` | 96 | 0.7362 | 0.6797 | 0.9722 | 0.9792 | 0.0s |

Trajetória (faithfulness / relevancy): hybrid `0.68→0.27→0.41 / 0.66→0.38→0.53`; clarify_fixo `0.73→0.35→0.47 / 0.70→0.43→0.58`; routed `0.86→0.48→0.54 / 0.78→0.59→0.66`; direct `0.18→0.13→0.15 / 0.82→0.81→0.80`; tree `0.86→0.78→0.74 / 0.71→0.74→0.68`.

Gráfico: `comparacao_2_vs_8_pops.png` (figura 2x2, um painel por métrica, 5 braços x 3 conjuntos).

## 4. Arquitetura — como descrever o sistema no TCC

```
data/pops/*.md (8 POPs)
  │
  ▼
ragbench index → Knowledge Graph LightRAG (entidades+relações+vetores 768d)
  │               lightrag_ollama_db/ + IndexManifest SHA256
  ▼
ragbench generate-dataset → golden_dataset.json (EDGE_CASE/ADVERSARIAL + ground_truth)
  │
  ▼
ragbench run / run-clarify / run-direct / run-tree → lote async + SQLite checkpoint
  │               runs/<run-id>/checkpoint.sqlite3 + manifests
  ▼
ragbench eval → RAGAS juiz Gemini → ragas_evaluation_results.csv + resumo_qualidade_ragas.md
```

Princípios (`AGENTS.md`): **Ports & Adapters** (`core/` puro em Pydantic v2, sem dependência externa; `engines/` adapta LightRAG/baselines; `infrastructure/` implementa HTTP/cache/storage), resiliência para 1000+ queries (`asyncio.Semaphore`, checkpoint atômico por query, `--resume`, backoff/jitter, `QuotaExhaustedError exit 3`), sem `dict` genérico entre módulos.

Componentes (`src/ragbench/`, ~6943 linhas):

- `config.py`: `BenchmarkSettings` via `pydantic-settings` (delimitador `__`). Modelos por papel: `LIGHTRAG__LLM_MODEL`, `CHAT__LLM_MODEL=gemini-3.1-flash-lite`, `RAGAS__JUDGE_MODEL` (eras avaliadas em `gemini-3.5-flash-lite`); embeddings fonte única `gemini-embedding-001/768` via REST `:embedContent` (endpoint OpenAI-compatível retorna 501 para `/embeddings`). Rate-limit `4.2s`, `concurrency=10`.
- `engines/lightrag_engine.py`: `LightRAGEngine(role=index|chat)` sobre `ResilientOllamaClient`. Ontologia bancária injetada na extração: `REGRA_BACEN, PROCEDIMENTO, SISTEMA, CONDICAO, EXCECAO, ATOR, DOCUMENTO, PRAZO` + few-shot. `_SafeCallable` contorna `RLock deepcopy`. `aget_context()` audita retrieval sem gerar.
- `conversational/router.py + clarifier.py`: roteador **só-grafo generalizado N-POPs (v2)** — recall ponderado da query sobre entidades reais de `kv_store_full_entities.json` (exclusivo 1.0, compartilhado 0.25; denominador = tokens da query, nunca tamanho do doc), margem `≥0.05` como parada, pergunta o slot mais discriminativo primeiro; bônus de keywords normativas (mesmo vocabulário da árvore) só para desempate; `load_entity_index` descobre POPs via `DOCUMENTO_ORIGEM:` (sem hardcoded); slots genéricos e `question_for_slot()` para novos POPs; query roteada aditiva (`k=v` + `[Resumo para o assistente]`); `ROUTED_SYSTEM_SUFFIX` automático no system; histórico de turnos no `aquery` (`user_prompt` por chamada); probe de reparo genérica N-docs. Corrigidos no caminho: `código de barras` → falso `codigo_bloqueio`, feedback loop do Resumo no re-routing, manifest parcial em resume (merge por índice).
- `engines/direct_llm_engine.py`: baseline `mode=direct`. `engines/decision_tree_engine.py` (~1100L): chatbot simbólico, v1 ~40 ramos (2 POPs) → v2 8 POPs + anti-colisão, templates fixos.
- `runner.py`: `BenchmarkRunner.execute_batch()` — cache semântico → `aquery()` → `save_record` por query, `quota_stop`, `asyncio.to_thread` para SQLite.
- `evaluation/ragas_evaluator.py`: `GeminiRestEmbeddings`, `AnswerRelevancy(strictness=1)` (Gemini rejeita `n=3`), `RunConfig(max_retries=15, max_wait=180)`, alerta NaN só em colunas de score.
- `cli.py + cli_commands/`: `health, config-check, index, generate-dataset, run, run-clarify, run-direct, run-tree, probe-retrieval, eval, chat, chat-clarify`.
- `infrastructure/`: `ollama_client.py`, `storage.py`, `semantic_cache.py`, `logging.py` (`logs/` rotativo + por run), `secrets.py` (`SecretStr` + scrub), `index_manifest.py + index_reconcile.py`.

## 5. Execução — protocolo replicável

```bash
uv pip install -e ".[all]"
cp .env.example .env  # preencher OLLAMA__API_KEY com chave Gemini
uv run ragbench health
uv run ragbench config-check
uv run ragbench index
uv run ragbench index --pops-dir data/pops --force  # rebuild total
uv run ragbench generate-dataset --questions-per-doc 5  # → data/golden_dataset.json
uv run ragbench run --run-name golden_full_hybrid_96 --mode hybrid --top-k 5
uv run ragbench run-clarify --run-name golden_clarify_fixo
uv run ragbench run-clarify --routed --run-name golden_routed
uv run ragbench run-direct --run-name golden_direct_completa_96
uv run ragbench run-tree --run-name golden_tree_v2
uv run ragbench probe-retrieval --query "senha bloqueou U site" --mode hybrid
uv run ragbench run --run-name X --resume  # retoma checkpoint.sqlite3
uv run ragbench eval --run-id golden_routed
```

Detalhes: chunk `1500/128`, idioma `Portuguese`, timeout LLM `2400s`, `max_async=1` no index; `--concurrency 10` respeita 4.2s do Gemini; telemetria por query (`total_latency, rag_latency, ttft, source{engine|cache}`). `runs/` tem 30+ pastas. Latências do nível 3 são genuínas (**0.0% cache-hit** em `resumo_benchmark.md`); evals `*_96` rodaram 02–05/10 atravessando janelas 429/503 com retries (oscilação do juiz `~±0.05`).

Curadoria de cenários: `hypothesis_inicial_scenarios.json` (ex. `acesso_bloqueio_u8_site` — senha 6d bloqueio `U` + biometria 5 dias + sem Alfa Code → “só presencial”) e `golden_scenarios_completa.json` (ex. `golden96-01` — varredura SISJUD de 2 anos inválida, limite 1 ano). Cada item: `id, pergunta_completa/incompleta, slots_esperados/simulados, ground_truth, source_document, tipo`.

Consolidação (cf. `PROMPT-regenerar-relatorio.md`): extrair médias de `resumo_qualidade_ragas.md`, `n`/latência de `benchmark_analise_detalhada.csv` via `csv.DictReader`, gerar PNG 2x2 com matplotlib, copiar 10+ CSVs + manifests + 3 JSONs de cenários para `evidencias/`, gerar `tabela_bracos_2_vs_8.csv`.

## 6. Leitura dos resultados (para Discussão)

1. **Grafo puro colapsou e recuperou só em parte** (`0.68→0.27→0.41`): competição vetorial entre domínios; recuperação parcial é efeito do mix de 96, não clarify (hybrid não clarifica). Latência 90.8s confirma busca ambígua. Ressalva: baseline 2 POPs tem `n=4`.
2. **Roteamento mitigou, não salvou** (`0.86→0.48→0.54`): restringir modo por doc reduz vazamento; melhor braço com grafo em 8 POPs.
3. **Do 16 para o 96, clarify passou a funcionar** (0 turnos → 1.44 médio no fixo, 1.24 no roteado; slots preenchidos): explica `0.35→0.47 (+34%)` e `0.48→0.54 (+14%)`; recall/precision saem de `1.0000` artificial para `0.96–0.99`.
4. **Árvore mais resistente** (`0.86→0.78→0.74`): template sem retrieval; custo é manutenção manual.
5. **Só-LLM é o piso** (`0.18→0.13→0.15`, relevancy `~0.80`): boa forma, conteúdo errado.
6. **Degradação em faithfulness/relevancy**, recall/precision `0.96–1.00`: contexto contém a resposta, gerador ancora no trecho errado.
7. Tuning revertido 27/09 (sobre 16): `k10→k5` + sem `[Dados coletados]` + prompt rígido → `0.4783→~0.25`. **Revertido**; 96 já refletem o revert.

## 6b. Série v2 — roteador N-POPs (06–09/10/2026)

Motivação: o roteador original fora tunado para 2 docs (`local/k10` acesso,
`hybrid/k5` CDC; demais POPs em fallback) e o scoring (fração do doc) inflava
POPs com poucas entidades quando aplicado aos 8 docs (5/24 rotas corretas nos
cenários hipótese). Correções (ver seção 4) elevaram o roteamento offline para
24/24 nos 24 e 61/96 nos 96 (teto manual da árvore: 72/96; judicial tem só 11
entidades e queries curtas empatam em tokens genéricos).

Runs `*_v2_24` / `golden_*_v2` (mesmos cenários-fonte; juiz
`gemini-3.5-flash-lite`; evidências `evidencias/erav2_*` + linhas
`2pops-24-v2`/`8pops-96-v2` na tabela-máquina):

| Braço | n=24 faith (antes) | n=96 faith (antes) |
|---|---|---|
| Routed N-POPs | 0.8579 (0.8588) | 0.5485 (0.5439) |
| Clarify fixo | 0.6909 (0.7349) | 0.4589 (0.4731) |
| Árvore v2 | 0.8576 (0.8631) | 0.7162† (0.7362) |

† Média sobre 79/96 (17 NaN: juiz não extraiu declarações de templates curtos).

Conclusões: sem regressão na generalização; routed confirma a hipótese nos 8
POPs (+0.09 sobre o fixo nos 96); árvore segue líder nos 96; `answer_relevancy`
do routed cede ~0.05 no 96 (Resumo alonga a pergunta — mover instrução para
`user_prompt` é o próximo tuning). Operação: egress IPv6 intermitente
(workaround `PYTHONPATH` forçando IPv4), cotas free-tier (embeddings 1000/dia,
juiz 500/dia → 1 eval-96/dia), `health` não faz I/O de rede (só checa a chave).

## 6c. Robustez fora de cobertura — OOD-32 (10/2026)

Conjunto `data/ood_scenarios.json` (32 cenários verificados por grep como sem
cobertura: 6 off-domain, 8 banking-não-coberto, 6 near-miss, 4 cross-POP, 8
armadilhas numéricas; gabaritos = comportamento esperado, revisados item a
item). Runs `ood_routed/hybrid/direct_completa/tree` + rúbrica A/B/C com dano
ponderado (B1 confirma/arbitra ×3/×2, B2 nega+desvia ×1, B3 fora-do-tema ×0).
Resultado (A/B1/B2/B3/C/dano): routed 20/3/9/0/0/18, hybrid 18/5/8/0/1/23,
direct 12/13/3/3/1/37, tree 0/18/0/0/14/51. A árvore não deu nenhum FALLBACK:
13 esclarecimentos irrelevantes + 18 templates confiantes em armadilhas; o
routed é o que mais se abstém honestamente (20/32, efeito do system prompt
anti-alucinação) e o direct o mais perigoso (13 confirmações, incluindo
receita/filme/gramática). Detalhes, tabela e limitações (ruído do juiz em
entradas idênticas, métrica nova no modelo de chat) em
[`relatorio-2-vs-8-pops.md`](relatorio-2-vs-8-pops.md) (seção OOD) e
`evidencias/eraood_rubrica.csv`. Enquadramento para a banca: árvore = oráculo
closed-world (teto in-dist, frágil OOD); routed = melhor sistema que
generaliza *e* se abstém.

## 7. Ameaças à validade (copiar para Metodologia)

- 3 questionários diferentes + `n=4` no baseline — efeito-corpus confundido com efeito-questionário.
- Nível 2 subestima clarify (0 turnos); nível 3 corrige (1.44/1.24 turnos).
- Cache no nível 2 vs 0% no nível 3.
- Juiz único + instabilidade 02–05/10.
- `golden.json` do `hybrid_96` equivale às `pergunta_completa` de `cenarios_8pops.json`.
- Série v2: código em working tree (não commitado em 09/10); faithfulness da
  árvore nos 96 sobre 79/96 amostras (17 NaN por template curto, não por erro);
  1 NaN em faithfulness/relevancy do routed 24/96; latências v2 genuínas
  (0% cache-hit), porém menores que as originais (10.4s vs 40.5s nos 24) por
  0 reparos e menos retries.
- Série v2 mediu rota==source offline: 24/24 (hipótese) e 61/96 (golden) —
  erro de rota custa só a estratégia (modo/top_k), nunca filtra documento,
  pois o retrieval consulta o grafo inteiro.
