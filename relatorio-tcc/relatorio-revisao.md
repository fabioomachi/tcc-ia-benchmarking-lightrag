# Revisão independente do experimento — guia para quem não conhece o projeto

> Público-alvo: revisor (orientador, banca, colega) sem contato prévio com o
> código. Cada afirmação abaixo aponta diretamente para o arquivo, comando ou
> evidência que a sustenta — siga os links e reproduza.

## 1. O que é este projeto, em linguagem simples

- **RAG** (Retrieval-Augmented Generation): em vez de o modelo de IA responder
  “de cabeça”, o sistema primeiro **busca trechos de documentos** e depois gera
  a resposta **baseada nesses trechos**. Isso reduz invenção (“alucinação”).
- **Knowledge Graph RAG (LightRAG)**: além de buscar por similaridade, o
  sistema monta um **grafo** (rede de entidades e relações extraídas dos
  documentos, ex: “bloqueio U” → *exige* → “alteração presencial”) e navega
  nele para montar o contexto. Biblioteca em `src/ragbench/engines/lightrag_engine.py`.
- **RAGAS / LLM-as-a-Judge**: a qualidade é avaliada por **outro modelo de IA
  atuando como juiz**, que dá notas de 0 a 1. Código em
  `src/ragbench/evaluation/ragas_evaluator.py`.
- O pacote se chama **ragbench** (`src/ragbench/`), com CLI única
  (`src/ragbench/cli.py`, comando `ragbench`), arquitetura hexagonal
  documentada em `AGENTS.md`, e o experimento da hipótese vive na branch
  `hypothesis/teste-inicial`.

## 2. A hipótese testada

> “Com a base de grafos, conversar com o usuário para coletar os dados que
> faltam produz respostas mais acuradas do que responder de uma vez — e o
> próprio grafo indica o que ainda falta perguntar.”

Exemplo concreto (caso real do dataset): o usuário pergunta *“minha senha
bloqueou, como desbloqueio pelo site?”*. Faltam dados críticos (código de
bloqueio? tem Alfa Code? biometria há quantos dias?). O sistema pergunta,
preenche e só então consulta o grafo — em vez de chutar.

## 3. Dados utilizados (todos versionados no git)

| Dado | Arquivo | Conteúdo |
|---|---|---|
| POP de senhas | `data/pops/pop_acesso_pf.md` (28 KB) | Regras de senhas 6/8 dígitos, códigos de bloqueio (U, 8, Q…), Alfa Code, biometria (regra 7 dias), canais |
| POP de crédito | `data/pops/pop_cdc_pf.md` (29 KB) | Regras de CDC: cancelamento (linha 2881, DOC 800020), duplicidade boleto/débito, amortização, alçadas |
| Golden inicial | `data/golden_dataset.json` (4 perguntas completas com ground-truth) | Base do braço baseline |
| Cenários da hipótese | `data/hypothesis_inicial_scenarios.json` (24 cenários) | Cada cenário tem: `pergunta_incompleta` (vaga, como usuário real), `slots_simulados` (respostas do usuário fictício), `pergunta_completa`, `ground_truth` (resposta correta extraída do POP), `source_document`, `tipo` |

Cobertura dos 24 cenários: 12 por POP; tipos `CONDITIONAL_WORKFLOW` (8),
`ROLE_RESTRICTION` (6), `EDGE_CASE` (5), `REGULATORY_TIMELINE` (5).
Exemplo de cenário (id `acesso_bloqueio_u8_site`): incompleta
*“Minha senha bloqueou, como desbloqueio pelo site?”* → slots
`codigo_bloqueio=U, alfa_code=não, biometria_dias=5…` → ground-truth: “só
presencial, 8 dígitos antes da de 6”.

## 4. Como o experimento foi montado (os “braços” e as 4 dimensões)

Todos os braços usam o **mesmo modelo de chat** e o **mesmo juiz**, isolando
só o método de resposta. O experimento varia **4 dimensões independentes** —
cada braço é uma combinação explícita delas, e cada comando processa *todos*
os itens da entrada (ver seção 5):

1. **Método de resposta**: com grafo (LightRAG) vs sem grafo (LLM puro).
2. **Clarificação**: nenhuma vs fixa (3 turnos, ordem fixa) vs guiada pelo
   grafo (slot discriminativo, parada por margem, roteador de modo).
3. **Input no LLM puro**: pergunta completa vs incompleta (testa se a pergunta
   completa “salva” o modelo sem grafo — não salva).
4. **Modelo de chat**: 3.1 vs 3.5 (replicação: prova que o ganho é do método).

| Braço | Comando | Grafo? | Clarify | Input | Chat | Código que o implementa |
|---|---|---|---|---|---|---|
| Baseline LightRAG | `run` | hybrid/k5 | nenhuma | completa (4) | 3.1 | `src/ragbench/cli_commands/run_cmd.py` + `src/ragbench/runner.py` |
| Clarify fixo | `run-clarify` | hybrid/k5 | fixa (3 turnos) | incompleta (24) | 3.1 | `src/ragbench/cli_commands/run_clarify_cmd.py` + `src/ragbench/conversational/batch.py` (`simulate_clarification`) |
| Clarify roteado | `run-clarify` (roteador ligado) | **roteado** | **guiada p/ margem** | incompleta (24) | 3.1 | + `src/ragbench/conversational/router.py` (`route_by_graph`, `simulate_clarification_guided`): slot discriminativo primeiro, parada por margem, modo por documento (acesso→`local/k10`, CDC→`hybrid/k5`) |
| LLM direto | `run-direct --input completa\|incompleta` | **NÃO** | nenhuma | completa/incompleta (24) | 3.1 | `src/ragbench/engines/direct_llm_engine.py` + `src/ragbench/cli_commands/run_direct_cmd.py`: **zero grafo/retrieval**, só conhecimento geral |
| Árvore decisão | `run-tree` | **NÃO (regras)** | guiada p/ slots | incompleta (24) | — | `src/ragbench/engines/decision_tree_engine.py` + `src/ragbench/cli_commands/run_tree_cmd.py`: ~40 ramos dos 2 POPs, templates fixos, `mode=tree` + `source=tree_engine` |
| Série `_35` | mesmos 4 comandos | idem | idem | idem | **3.5** | Mesmos arquivos; só `CHAT__LLM_MODEL` trocado no `.env` |

Configuração dos modelos: `src/ragbench/config.py` (+ `.env`, não versionado;
template em `.env.example`). Na época dos experimentos: index
`gemini-3.5-flash-lite`, chat `gemini-3.1-flash-lite` (série `_35`: chat
`gemini-3.5-flash-lite`), juiz `gemini-3.5-flash-lite`, embeddings
`gemini-embedding-001`/768. Detalhes em `relatorio-tcc/evidencias/ambiente.md`.

## 5. Como os testes foram feitos (3 camadas, todas reproduzíveis)

### Camada 1 — Testes unitários (158, sem rede, sem custo)

```bash
uv run pytest tests/ --no-cov -q   # esperado: 158 passed
uv run ruff check src/ragbench tests/unit/test_clarifier.py tests/unit/test_direct.py tests/unit/test_router.py tests/unit/test_run_clarify.py tests/unit/test_tree.py
```

> O que cada teste verifica, linha a linha (tabela por ramo da árvore
> incluída): `relatorio-tcc/evidencias/testes-detalhados.md`. Resumo por
> arquivo abaixo.

| Arquivo de teste | O que prova (aponte direto) |
|---|---|
| `tests/unit/test_clarifier.py` | Extração de slots (ex: `bloqueio 'U'` → `codigo_bloqueio=U`), regressão do bug “bloqueio **p**elo capturava P”, loop interativo, limite de turnos |
| `tests/unit/test_router.py` | Scoring só-grafo (overlap ponderado com entidades do índice), margem, fallback sem índice, simulação guiada com parada precoce |
| `tests/unit/test_run_clarify.py` | `run-clarify` gera os mesmos artefatos do `run` + manifest; simulação pula slots sem valor em vez de travar |
| `tests/unit/test_direct.py` | LLM-direto não injeta contexto/chunks, lifecycle no-op, records marcados `mode=direct` + `source=baseline_engine` |
| demais (`test_cli.py`, `test_config.py`, `test_runner_checkpoint.py`…) | CLI, configurações, checkpoint/resume, storage, RAGAS — regressão do framework |

### Camada 2 — Probe de retrieval (barata: só busca, sem gerar resposta)

```bash
uv run ragbench probe-retrieval --run-name probe_demo --top-k 10
# saída: runs/probe_demo/retrieval_probe.{json,md}
```

Para cada cenário × modo (`naive/local/global/hybrid`), busca **só o contexto**
(`LightRAGEngine.aget_context`, em `src/ragbench/engines/lightrag_engine.py`)
e classifica qual documento dominou. Evidência commitada:
`relatorio-tcc/evidencias/probe_piores_5.md` — **0/20**: todos os modos
recuperavam o doc errado (CDC) para perguntas de senhas, inclusive frase
literal do POP. O comparativo top_k está em
`relatorio-tcc/evidencias/sweep_topk.md` (hybrid 0/5 em qualquer k; local/k10
5/5 no acesso mas 1/4 no CDC — daí o roteador).

### Camada 3 — Runs + julgamento RAGAS (custa tempo/cota Gemini)

```bash
uv run ragbench run --run-name EXP --target data/golden_dataset.json --mode hybrid --no-resume
uv run ragbench run-clarify --run-name EXP --mode hybrid --max-clarify-turns 3 --no-resume
uv run ragbench run-direct --input completa|incompleta --run-name EXP --no-resume
uv run ragbench eval --run-id EXP
```

Cada run grava em `runs/<id>/`: `checkpoint.sqlite3` (respostas + latências),
`benchmark_analise_detalhada.csv`, `resumo_benchmark.md`, `clarify_manifest.json`
ou `direct_manifest.json` (auditoria: slots, turnos, rota, margem por pergunta)
e `golden.json` (para o `eval` casar pergunta↔ground-truth por texto exato).
O `eval` acrescenta `ragas_evaluation_results.csv` (notas por pergunta) e
`resumo_qualidade_ragas.md`. Cópias das evidências de cada braço estão em
`relatorio-tcc/evidencias/*_ragas.csv`.

## 6. Resultados (lidos direto das evidências)

Tabela completa computada de `relatorio-tcc/evidencias/*_ragas.csv`
(ver também `tabela_bracos.csv` e `por_tipo.csv`):

| Braço | n | Faithfulness | Relevancy |
|---|---|---|---|
| Roteado (3.1 / 3.5) | 24 | **0.859 / 0.872** | 0.78 |
| Clarify fixo | 24 | 0.735 | 0.70 |
| Baseline | 4 | 0.68–0.71 | 0.66 |
| Direto (4 variantes) | 24 | 0.15–0.24 | **0.82–0.84** |

Tradução para não-técnicos: com grafo+roteador, ~86% do que o sistema afirma
é sustentado pelos documentos; sem grafo, ~15–24% — mas o texto continua
fluente e pertinente (relevancy 0.82). **Fluência não é conhecimento**: essa
combinação (relevancy alta + faithfulness baixa) é a assinatura mensurada da
alucinação confiante. O ganho se replica nos dois modelos de chat, logo vem
do método, não do modelo.

## 7. Como replicar do zero (receita)

```bash
git clone https://github.com/fabioomachi/tcc-ia-benchmarking-lightrag.git
cd tcc-ia-benchmarking-lightrag && git checkout hypothesis/teste-inicial
cp .env.example .env   # preencher OLLAMA__API_KEY com a chave do Gemini
uv pip install -e ".[all]"
uv run ragbench health                       # valida transporte
uv run ragbench index                        # constrói o grafo a partir de data/pops/
uv run ragbench run-clarify --run-name REP --no-resume
uv run ragbench eval --run-id REP
uv run pytest tests/ --no-cov -q             # 158 passed
```

Notas de custo: cada eval de 24 amostras ≈ 96 tarefas do juiz (≈ 7–15 min);
cota free-tier 500 req/dia/modelo — um braço completo (run+eval) consome parte
relevante; espaçar braços ou usar chave com cota maior. O `eval` do 4º braço
(`exp_direct_incompleta`) chegou a travar 2× por cota antes de concluir —
registrado como limite, não como dado perdido (a run estava íntegra).

## 8. Limites conhecidos (para a banca não perguntar primeiro)

1. n=24: indício forte, não prova estatística formal.
2. `context_precision/recall ≈ 1.0` é artefato: o `eval` usa o arquivo-fonte
   como contexto do RAGAS (`src/ragbench/evaluation/ragas_evaluator.py`,
   `prepare_dataset`), não os chunks recuperados — o retrieval real foi medido
   pela probe (camada 2), não por essas colunas.
3. Cache do LightRAG acelerou runs (latências otimistas).
4. Extração de entidades do índice é genérica (tipos `organization`/`artifact`),
   não a ontologia bancária injetada no prompt — o roteador contorna o viés de
   ranking, não o cura (reindexação como trabalho futuro).
5. Juiz `3.7-flash` existe no endpoint mas tem cota de 20 req/dia (inviável);
   mantido `3.5-flash-lite`.

## 9. Mapa de arquivos (índice de auditoria)

- Hipótese→código: clarificador `conversational/clarifier.py`, roteador
  `conversational/router.py`, simulação `conversational/batch.py`
- Braços: `cli_commands/run_cmd.py`, `run_clarify_cmd.py`, `run_direct_cmd.py`,
  `probe_cmd.py`, `clarify_cmd.py`, `chat_cmd.py`
- Motores: `engines/lightrag_engine.py`, `engines/direct_llm_engine.py`
- Contratos: `core/models.py` (`SearchMode` com `DIRECT`, `QueryInteractionSource`
  com `BASELINE_ENGINE`), `core/interfaces.py`, `config.py` (`ClarifySettings`,
  `RoutingSettings`)
- Avaliação: `evaluation/ragas_evaluator.py`, `reporting/reporters.py`,
  `infrastructure/storage.py` (checkpoint SQLite), `runner.py`
- Dados: `data/pops/*.md`, `data/golden_dataset.json`,
  `data/hypothesis_inicial_scenarios.json`
- Evidências: `relatorio-tcc/evidencias/` (9 CSVs RAGAS, manifests, probes,
  cenários, piores casos, ambiente) · relatório técnico:
  `relatorio-tcc/relatorio-hipotese.md`
