# Timeline do projeto `ragbench` — 06/09 a 09/10/2026

> **Documento complementar:** ver também [`relatorio-desenvolvimento-execucao.md`](relatorio-desenvolvimento-execucao.md) — desenvolvimento, protocolo de execução, matriz 3 níveis x 5 braços e leitura dos resultados.
> **Resultado experimental:** ver [`relatorio-2-vs-8-pops.md`](relatorio-2-vs-8-pops.md) — matriz, gráfico `comparacao_2_vs_8_pops.png` e evidências em [`evidencias/`](evidencias/).

Repositório: `github.com/fabioomachi/tcc-ia-benchmarking-lightrag` — branch `main`, **57 commits** (+ working tree v2 não commitado em 09/10), conferido no GitHub (`/commits/main`) + `git log --reverse` local. Todos os hashes abaixo são verificáveis em `/commit/<hash>`.

## Fase 0 — PoC com scripts soltos — 06/09

Objetivo: provar que LightRAG + Ollama local indexava POP bancário e respondia.

| Data | Commit | O que foi feito | O que mudou / por quê |
|---|---|---|---|
| 06/09 | `ba737b4` reinicializa repo limpo | Cria `input/pop_bloqueio_cartao.txt`, `pop_cancelamento_pix.txt`, `src/1_indexacao.py (99L)`, `2_consulta.py (55L)`, `run_poc.py`, `script-bdgrafos.py`, `requirements.txt (118L)` | Sai de pasta aninhada para raiz do TCC. Arquitetura ainda procedural |
| 06/09 | `aa3e7e0`, `32dbc49` | Ajustes readme/estrutura | Organização inicial |
| 06/09 | `0d27419`, `585a3bd` | Logging estruturado + cache semântico + `script_analisa_logs.py` | 1ª preocupação com repetição e custo LLM |
| 06/09 | `73b5db7` | Primeira análise RAGAS | LLM-as-a-Judge desde o dia 1 |

## Fase 1 — Dataset adversarial + primeiros gargalos — 07–08/09

| Data | Commit | O que foi feito | O que mudou |
|---|---|---|---|
| 07/09 | `b0b134b` | Importação POPs + respostas em lote | Sai de 1 pergunta para N |
| 07/09 | `5dd4cbe` | Fix “não gerava grafos” | Ambiente/entidades LightRAG |
| 07/09 | `f1e7c59`, `7872335`, `00f6c5d`, `136b261`, `9c0b52b` | Limpa logs antes de indexar + pastas/readme | Higiene de experimento |
| 07/09 | `40c61b0` | `script_gera_perguntas.py (150L)` — 10 q/doc `EDGE_CASE`, prazos regulatórios, compliance + `script_analisa_ragas.py (152L)` com `ground_truth`, `context_recall/precision` | **Virada metodológica:** dataset vira adversarial |
| 07/09 | `c140843` | Troca embedding do avaliador (`all-minilm` → contexto estendido, fim do HTTP 500), juiz maior, tuning `num_ctx/num_predict` anti-OOM VRAM, estrangula concorrência anti-timeout | **1º diagnóstico infra:** Ollama local estoura VRAM/timeout em lote |
| 07/09 | `c927f65` | Readme Ollama | Documenta dependência local |
| 08/09 | `f2ffd93` | Fix RAGAS pegava pergunta errada | Corrige join pergunta/resposta |

## Fase 2 — Vira framework `ragbench` — 09–10/09

Maior ruptura arquitetural. Detalhes da arquitetura resultante em [`relatorio-desenvolvimento-execucao.md`](relatorio-desenvolvimento-execucao.md) (seção 4).

| Data | Commit | O que foi feito |
|---|---|---|
| 09/09 | `ca53d9d` | Cria `src/ragbench/` (`cli.py 336L`, `config.py`, `core/`, `engines/lightrag_engine 134L`, `evaluation/`, `infrastructure/`, `reporting/`, `runner.py 194L`) + `pyproject.toml 85L` + `AGENTS.md` + `.env.example`. Ports & Adapters, `uv`, `pydantic`, `sqlite checkpointing` |
| 09/09 | `8c6d5ee` | Fix `QueryParam` + `RLock deepcopy` (`_SafeCallable`) |
| 09/09 | `647f09d` | Deleta `1_indexacao.py`, `2_consulta.py`, `script_*.py`, `prompts/`, `requirements.txt`; move `entradas/pops → data/pops/`; cria `data/golden_dataset.json`; reescreve readme; `uv.lock 3752L` |
| 10/09 | `60f4955` | Ajuste fino máquina local |

Efeito: de scripts descartáveis para sistema instalável (`uv pip install -e .[all]`), retomável (`--resume`), configurável (`.env` nested `__`).

## Fase 3 — Migração Ollama → Gemini + qualidade — 13/09

| Data | Commit | O que foi feito |
|---|---|---|
| 13/09 | `96d9e7b`, `0b97cfc` | Dual-model index/chat, workers/embeddings unificados, correção AI Studio |
| 13/09 | `dee32e2`, `0707e24`, `e0100a0` | Fixes eval `.md` |
| 13/09 | `1fad9bc` | **Transporte Gemini unificado:** chat usa mesmo pipeline resiliente do index, só muda `CHAT__LLM_MODEL`; eval usa juiz dedicado via `ChatOpenAI` + `strictness=1` |
| 13/09 | `c18a0f6` | `OllamaChatClient` → REST nativa `/api/chat`, relatório defensivo, checkpoint por query |
| 13/09 | `f0d69d4` | 87 testes fases 0-4, gate `coverage 80%`, DI, CLI modular (`cli_commands/`), settings lazy |
| 13/09 | `47670cd`, `456cdaa` | Readme por papel; logs centralizados `logs/` com rotação + por run |

Efeito: Ollama vira fallback `health`; padrão é Gemini.

## Fase 4 — Hipótese conversacional — 16–18/09 (Era 2 POPs)

Pergunta passa a ser: *clarificar guiado pelo grafo supera single-turn?* Números desta era na matriz Nível 1 de [`relatorio-desenvolvimento-execucao.md`](relatorio-desenvolvimento-execucao.md) (seção 3).

| Data | Commit | O que foi feito |
|---|---|---|
| 16/09 | `9bbe766` (+2370L) | `conversational/clarifier.py 182L + router.py 198L + batch.py`, `run-clarify 259L`, `run-direct 168L + DirectLLMEngine 83L`, `probe-retrieval 189L`, `data/hypothesis_inicial_scenarios.json 320L` (24 cenários). Roteador só-grafo (overlap ponderado, margem `≥0.05`, `local/k10` acesso vs `hybrid/k5` CDC, 23/24) |
| 16/09 | `d321244` (+2313L) | `relatorio-hipotese.md` + evidências (`baseline 4`, `clarify 24`, `roteado 24`, `direto 24`, `sweep_topk`, piores casos). `routed 0.859 vs fixo 0.735 vs direto 0.183` |
| 17/09 | `9ec2cd4` | Matriz 5 braços + série `_35` + limites cota |
| 18/09 | `f4558f9`, `c229e03`, `47ca8f6`, `3a5c646` | Fecha `direct_35`, conclusão 9 avaliações, guia leigos + auditoria, matriz 4 dimensões |
| 18/09 | `b38254e` (+1299L) | **5º braço:** `DecisionTreeEngine 537L` (~40 ramos), `SearchMode.TREE`, `run-tree`, `test_tree`. `exp_tree_24: 0.8631, 0 fallbacks` |
| 18/09 | `ea2b7b2`, `ee83ced`, `3302374`, `987e5b5`, `35b72dd` | Anexo 158 testes, coluna definição cenário, seção TCC no readme |

Execução da era: `runs/exp_*` (16–18/09), `n=24` exceto baseline `n=4`.

## Fase 5 — Endurecimento + escala 2→8 POPs — 26/09–05/10

Números finais na matriz Níveis 2–3 de [`relatorio-desenvolvimento-execucao.md`](relatorio-desenvolvimento-execucao.md) (seção 3).

| Data | Commit | O que foi feito |
|---|---|---|
| 26/09 | `c1a2dd6` | Index incremental `SHA256` + `reconcile.py`, `QuotaExhaustedError exit 3`, +6 POPs anonimizados, parser envelope-lista |
| 26/09 | `ed00169`, `29456a3` (revert), `5e9899a` | Série golden-8 entra/sai; `SecretStr` + scrub + `config-check` |
| 26/09 | `4033283` (+924L) | Árvore v2 8 POPs + anti-colisão |
| 27/09 | `3cb73b8`, `bacb609`, `5456cec` (+4909L), `52e7b02`, `57c0157` | Comparativo 2 vs 8 POPs + PNG + `PROMPT-regenerar`, remove antigos, fix latência árvore. Tuning revertido `k10→k5` → `0.47→0.25`, **revertido** |
| 02/10 | `1940c47` (+9339L) | Golden **16→96** (`golden96-00`…`95`, 12/POP, `incompleta≠completa`), re-executa clarify/routed/tree nos 96 |
| 02/10 | `f141de6` | Preserva intermediário 16 como controle (`era8_16_*`, `cenarios_8pops_16.json`). Matriz vira 3 níveis |
| 05/10 | `9cb5b85` | Fecha nível 96 com `hybrid_96 0.4050/0.5317` + `direct_96 0.1534/0.8016` |

Estado final: `golden_scenarios_completa.json` 96 itens, `relatorio-2-vs-8-pops.md` 3 níveis, `tabela_bracos_2_vs_8.csv` 15 linhas, `evidencias/` 11MB (32 arquivos), `runs/` 30+ pastas.

## Fase 6 — Roteador N-POPs + série v2 — 06–09/10 (working tree, sem commit)

Auditoria do `run` roteado mostrou que o roteador 2-docs quebrava com 8 POPs
(scoring por fração do doc inflava POPs pequenos: 5/24 rotas certas). Correções
sem regra por documento: recall sobre a query, stopwords (`meu/não/…`), valores
crus fora do scoring, bônus de keywords normativas p/ desempate, query aditiva
`k=v` + `[Resumo para o assistente]`, system prompt de roteamento, histórico no
`aquery`, probe genérica, fix `código de barras`→`codigo_bloqueio` e do feedback
loop do Resumo, merge de manifest em resume. Offline: 24/24 (hipótese) e 61/96
(golden; teto árvore 72/96).

Série v2 (juiz `gemini-3.5-flash-lite`; evidências `evidencias/erav2_*`, tabela
`2pops-24-v2`/`8pops-96-v2`): routed 0.8579 (24) / 0.5485 (96) ≈ legado
0.8588/0.5439; fixo 0.6909/0.4589; tree 0.8576/0.7162† (†79/96, templates curtos).
Routed confirma a hipótese nos 8 POPs (+0.09 vs fixo nos 96). Operação: IPv6
intermitente (workaround `PYTHONPATH`→IPv4), cotas free-tier (embed 1000/dia,
juiz 500/dia → 1 eval-96/dia), `health` sem I/O real.

## Síntese para a banca (1 parágrafo por virada)

1. **07/09:** local não aguenta lote → troca embeddings/juiz + throttling.
2. **09/09:** scripts → framework retomável e testável.
3. **13/09:** local → Gemini unificado + 87 testes.
4. **16/09:** modo LightRAG → hipótese clarify+router só-grafo.
5. **18/09:** só neural → teto simbólico (árvore 0.86 empata grafo).
6. **26/09–05/10:** 2→8 POPs→96 golden revela colapso parcial do grafo (`0.68→0.27→0.41`), mitigação do roteamento (`0.86→0.48→0.54`), imunidade relativa da árvore (`0.86→0.78→0.74`).
7. **06–09/10:** roteador vira N-POPs sem regra por documento (24/24 e 61/96 rotas certas); série v2 confirma hipótese nos 8 POPs (routed 0.55 vs fixo 0.46 nos 96) sem regressão vs legado.

Ver interpretação completa em [`relatorio-desenvolvimento-execucao.md`](relatorio-desenvolvimento-execucao.md) (seções 6–7).
