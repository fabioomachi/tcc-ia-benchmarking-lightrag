# ragbench — RAG Benchmarking Framework

Framework de benchmarking para arquiteturas **RAG (Retrieval-Augmented Generation)**, especializado em **Knowledge Graph RAG** com transporte unificado via API Gemini (OpenAI-compatível) e avaliação analítica com **LLM-as-a-Judge** via [RAGAS](https://docs.ragas.io). Ollama local é mantido apenas como fallback.

Desenvolvido como projeto de TCC sobre avaliação de arquiteturas de IA para domínios regulatórios.

## TCC — estudo conduzido neste repositório

**Pergunta de pesquisa:** com a base de grafos, conduzir clarificação para
coletar os dados que faltam produz respostas mais acuradas do que o
single-turn direto — e o próprio grafo indica o que ainda falta perguntar?

**Desenho:** 24 cenários sobre 2 POPs bancários (senhas e CDC), avaliados em
até 5 braços (LightRAG, clarify fixo, clarify roteado, LLM puro, árvore de
decisão) com juiz RAGAS, nos mesmos modelos — [matriz completa e
metodologia](https://github.com/fabioomachi/tcc-ia-benchmarking-lightrag/tree/main/relatorio-tcc).

**Resultado principal:** grafo + roteador ≈ 0.86 de faithfulness contra ≈ 0.2
do LLM puro (~4–5×); árvore de decisão empatada (0.86) como teto simbólico.

**Dados e relatório do estudo** (pasta `relatorio-tcc/` na `main`):

- [Relatório da hipótese](https://github.com/fabioomachi/tcc-ia-benchmarking-lightrag/blob/main/relatorio-tcc/relatorio-hipotese.md) — tabelas, leitura das métricas, limites
- [Guia de revisão para leigos](https://github.com/fabioomachi/tcc-ia-benchmarking-lightrag/blob/main/relatorio-tcc/relatorio-revisao.md) — dados, replicação, mapa de auditoria
- [Evidências](https://github.com/fabioomachi/tcc-ia-benchmarking-lightrag/tree/main/relatorio-tcc/evidencias) — RAGAS por pergunta, manifests, probes, cenários, testes linha a linha

---

## Visão Geral

```
POPs (documentos-fonte)
        │
        ▼
┌─────────────────┐
│  ragbench index │  → Indexa documentos no LightRAG (Knowledge Graph)
└────────┬────────┘
         │
         ▼
┌────────────────────────┐
│ ragbench generate-     │  → Gera Golden Dataset adversarial (LLM-as-author)
│         dataset        │
└────────┬───────────────┘
         │
         ▼
┌─────────────────┐
│  ragbench run   │  → Executa benchmark em lote (async + checkpointing SQLite)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ragbench eval  │  → Avalia qualidade com RAGAS (Faithfulness, Relevancy, etc.)
└─────────────────┘
```

---

## Pré-requisitos

| Dependência | Versão mínima | Observação |
|---|---|---|
| Python | 3.11+ | Usar 3.12 recomendado |
| [uv](https://docs.astral.sh/uv/) | 0.4+ | Gerenciador de pacotes |
| API key Google (Gemini) | — | Obrigatória; configurada em `OLLAMA__API_KEY` no `.env` |
| [Ollama](https://ollama.com) | qualquer | Opcional — apenas fallback local (`localhost:11434`) |

### Modelos por papel (transporte Gemini unificado)

Index, chat e eval compartilham o mesmo pipeline resiliente (rate-limit + retries + streaming) e se diferenciam **apenas** pelo nome do modelo:

| Papel | Variável | Padrão no código | Exemplo no `.env` |
|---|---|---|---|
| Index (LightRAG) | `LIGHTRAG__LLM_MODEL` | `qwen2.5:1.5b` | `gemini-3.5-flash-lite` |
| Chat / query | `CHAT__LLM_MODEL` | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` |
| Juiz RAGAS | `RAGAS__JUDGE_MODEL` | `gemini-3.8-flash` | `gemini-3.5-flash-lite` |
| Embeddings (fonte única) | `LIGHTRAG__EMBED_MODEL` / `RAGAS__EMBED_MODEL` | `gemini-embedding-001` (768 dim) | `gemini-embedding-001` |

> Os embeddings são sempre os do index (`gemini-embedding-001`/768 via REST `:embedContent`) — o endpoint OpenAI-compatível do Gemini não implementa `/embeddings` (retorna 501), por isso o eval usa REST nativo. Modelos sem prefixo `gemini-` usam o fallback Ollama local.

---

## Instalação

```bash
# Clonar o repositório
git clone https://github.com/fabioomachi/tcc-ia-benchmarking-lightrag.git
cd tcc-ia-benchmarking-lightrag

# Instalar dependências (cria .venv automaticamente)
uv pip install -e ".[all]"

# Configurar variáveis de ambiente (obrigatório: preencher OLLAMA__API_KEY com a chave do Gemini)
cp .env.example .env
```

---

## Estrutura do Projeto

```
tcc-ia-benchmarking-lightrag/
├── AGENTS.md                    # Diretrizes arquiteturais para agentes de IA
├── .env.example                 # Template de variáveis de ambiente
├── pyproject.toml               # Empacotamento, dependências e configuração de ferramentas
│
├── data/                        # Dados de entrada (versionados)
│   ├── pops/                    # Documentos-fonte para indexação
│   │   ├── pop_bloqueio_cartao.txt
│   │   └── pop_cancelamento_pix.txt
│   └── golden_dataset.json      # Dataset de perguntas + ground-truth para benchmark
│
├── src/
│   └── ragbench/                # Pacote principal (Hexagonal Architecture)
│       ├── cli.py               # Registro dos comandos Typer (wiring fino)
│       ├── cli_commands/        # Implementação dos comandos (health, index, dataset, run, eval, chat)
│       ├── config.py            # Configuração centralizada (Pydantic Settings)
│       ├── runner.py            # Orquestrador de benchmark assíncrono
│       ├── core/                # Domínio: modelos, interfaces, exceções
│       ├── engines/             # Adaptadores RAG (LightRAG)
│       ├── evaluation/          # Geração de dataset e avaliação RAGAS
│       ├── infrastructure/      # Cache semântico, storage SQLite/JSONL, clientes Gemini/Ollama
│       └── reporting/           # Geração de relatórios Markdown e CSV
│
├── tests/
│   └── unit/                    # Testes unitários (pytest, gate de cobertura 80%)
│
├── lightrag_ollama_db/          # Índice LightRAG em disco (gerado em runtime, git-ignored)
└── runs/                        # Resultados de benchmark por execução (git-ignored)
    └── <run-id>/
        ├── checkpoint.sqlite3           # Checkpoint atômico (suporte a --resume)
        ├── benchmark_analise_detalhada.csv
        ├── resumo_benchmark.md
        ├── ragas_evaluation_results.csv
        └── resumo_qualidade_ragas.md
```

---

## Uso — CLI `ragbench`

### Verificar ambiente

```bash
uv run ragbench health
```

### 1. Indexar documentos

Indexa todos os `.txt` da pasta `data/pops/` no Knowledge Graph LightRAG.

```bash
uv run ragbench index
# ou especificar diretório customizado:
uv run ragbench index --pops-dir caminho/para/docs/
```

### 2. Gerar Golden Dataset adversarial

Gera perguntas `EDGE_CASE` e `ADVERSARIAL` baseadas nos POPs, com ground-truth para avaliação RAGAS.

```bash
uv run ragbench generate-dataset --questions-per-doc 5
# Saída padrão: data/golden_dataset.json
```

### 3. Executar benchmark

Executa as perguntas do Golden Dataset em lote, com concorrência controlada e checkpointing atômico.

```bash
uv run ragbench run --run-name meu_experimento
```

Parâmetros disponíveis:

| Flag | Padrão | Descrição |
|---|---|---|
| `--target` | `data/golden_dataset.json` | Arquivo ou pasta de perguntas |
| `--mode` | `hybrid` | Modo LightRAG: `naive`, `local`, `global`, `hybrid` |
| `--top-k` | `5` | Chunks/entidades recuperados por consulta |
| `--concurrency` | `10` | Requisições concorrentes (respeitando o rate-limit do Gemini, 4.2s) |
| `--run-name` | `run_<timestamp>_<mode>` | Nome identificador da execução |
| `--resume` / `--no-resume` | `True` | Retoma de checkpoint anterior |

```bash
# Retomar execução interrompida
uv run ragbench run --run-name meu_experimento --resume

# Comparar modos de busca
uv run ragbench run --run-name exp_local --mode local
uv run ragbench run --run-name exp_global --mode global
uv run ragbench run --run-name exp_hybrid --mode hybrid
```

### 4. Avaliar qualidade (RAGAS)

```bash
uv run ragbench eval --run-id meu_experimento
```

Gera em `runs/meu_experimento/` (mais cópia em `resultados/`):
- `ragas_evaluation_results.csv` — métricas por pergunta
- `resumo_qualidade_ragas.md` — relatório com análise de casos críticos

Notas:
- O juiz usa `RAGAS__JUDGE_MODEL` via transporte Gemini (modelos `gemini-*`; demais caem no Ollama local).
- `answer_relevancy` roda com `strictness=1` no Gemini (o padrão `n=3` é rejeitado com 400 — múltiplos candidatos não suportados).
- Resiliência a 429/503 transitórios: `RAGAS__JUDGE_MAX_RETRIES=8`, `RAGAS__RUN_MAX_RETRIES=15`, `RAGAS__RUN_MAX_WAIT=180`. O alerta de NaN considera só as colunas de métrica (telemetria nula no checkpoint, ex: `ttft_s`, não conta).

### 5. Chat interativo

```bash
uv run ragbench chat --mode hybrid
# ou com override pontual do modelo de chat (mesmo pipeline, outro modelo):
uv run ragbench chat --chat-model gemini-3.1-flash-lite
```

Usa o mesmo pipeline resiliente do index, gerando com `CHAT__LLM_MODEL`, com cache semântico, histórico por janela deslizante e telemetria (latência total + TTFT).

---

## Métricas RAGAS

| Métrica | O que mede | Ideal |
|---|---|---|
| **Faithfulness** | O quanto a resposta é suportada pelo contexto recuperado (sem alucinações) | → 1.0 |
| **Answer Relevancy** | O quanto a resposta endereça a pergunta original | → 1.0 |
| **Context Recall** | O quanto o contexto recuperado cobre o ground-truth | → 1.0 |
| **Context Precision** | Proporção de chunks recuperados que são realmente relevantes (sem ruído) | → 1.0 |

---

## Desenvolvimento

```bash
# Linting e checagem estática
uv run ruff check .
uv run ruff format --check .

# Testes unitários (gate de cobertura: 80%)
uv run pytest tests/

# Instalar dependências de desenvolvimento
uv pip install -e ".[dev]"
```

---

## Arquitetura

O `ragbench` segue **Ports & Adapters (Hexagonal Architecture)** com transporte LLM unificado:

- **`core/`** — Domínio puro: schemas Pydantic, protocolos (`BaseRAGPipeline`, `BaseCache`), exceções. Zero dependência de frameworks externos.
- **`engines/`** — Adaptadores de RAG. `LightRAGEngine` (roles `index`/`chat`) sobre `ResilientOllamaClient` (Gemini). Index e chat diferem só no modelo (`LIGHTRAG__LLM_MODEL` ≠ `CHAT__LLM_MODEL`); embeddings sempre via index.
- **`infrastructure/`** — Implementações concretas de cache, storage e cliente HTTP. `SQLiteExecutionStorage` garante checkpointing atômico e suporte a `--resume` para runs de 1000+ perguntas. `OllamaChatClient` (REST nativa) mantido para fallback local e `health`.
- **`evaluation/`** — Pipeline de geração adversarial e avaliação LLM-as-a-Judge com juiz dedicado (`RAGAS__JUDGE_MODEL`, `GeminiRestEmbeddings` via REST).
- **`cli.py` + `cli_commands/`** — Ponto de entrada único. `cli.py` só registra os comandos Typer; a implementação vive em `cli_commands/` (um módulo por comando) com injeção via `deps` (testável com factories).