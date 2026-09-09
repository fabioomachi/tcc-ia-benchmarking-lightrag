# ragbench — RAG Benchmarking Framework

Framework de benchmarking para arquiteturas **RAG (Retrieval-Augmented Generation)**, especializado em **Knowledge Graph RAG** com inferência local via [Ollama](https://ollama.com) e avaliação analítica com **LLM-as-a-Judge** via [RAGAS](https://docs.ragas.io).

Desenvolvido como projeto de TCC sobre avaliação de arquiteturas de IA para domínios regulatórios.

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
| [Ollama](https://ollama.com) | qualquer | Rodando localmente em `localhost:11434` |

### Modelos Ollama necessários

```bash
ollama pull qwen2.5:7b          # LLM principal para consultas e geração de dataset
ollama pull qwen2.5:3b          # LLM de inferência (mais leve, para indexação)
ollama pull nomic-embed-text    # Embeddings semânticos (RAGAS)
ollama pull all-minilm          # Embeddings para o índice LightRAG
```

---

## Instalação

```bash
# Clonar o repositório
git clone https://github.com/fabioomachi/tcc-ia-benchmarking-lightrag.git
cd tcc-ia-benchmarking-lightrag

# Instalar dependências (cria .venv automaticamente)
uv pip install -e ".[all]"

# Configurar variáveis de ambiente (opcional — os defaults funcionam para Ollama local)
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
│       ├── cli.py               # Interface CLI (Typer)
│       ├── config.py            # Configuração centralizada (Pydantic Settings)
│       ├── runner.py            # Orquestrador de benchmark assíncrono
│       ├── core/                # Domínio: modelos, interfaces, exceções
│       ├── engines/             # Adaptadores RAG (LightRAG)
│       ├── evaluation/          # Geração de dataset e avaliação RAGAS
│       ├── infrastructure/      # Cache semântico, storage SQLite/JSONL, cliente Ollama
│       └── reporting/           # Geração de relatórios Markdown e CSV
│
├── tests/
│   └── unit/                    # Testes unitários (pytest)
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
| `--concurrency` | `10` | Requisições concorrentes ao Ollama |
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

Gera em `runs/meu_experimento/`:
- `ragas_evaluation_results.csv` — métricas por pergunta
- `resumo_qualidade_ragas.md` — relatório com análise de casos críticos

### 5. Chat interativo

```bash
uv run ragbench chat --mode hybrid
```

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

# Testes unitários
uv run pytest tests/

# Instalar dependências de desenvolvimento
uv pip install -e ".[dev]"
```

---

## Arquitetura

O `ragbench` segue **Ports & Adapters (Hexagonal Architecture)**:

- **`core/`** — Domínio puro: schemas Pydantic, protocolos (`BaseRAGPipeline`, `BaseCache`), exceções. Zero dependência de frameworks externos.
- **`engines/`** — Adaptadores de RAG. `LightRAGEngine` implementa `BaseRAGPipeline`. Novos motores (ex: GraphRAG, Chroma) podem ser adicionados sem alterar o core.
- **`infrastructure/`** — Implementações concretas de cache, storage e cliente HTTP. `SQLiteExecutionStorage` garante checkpointing atômico e suporte a `--resume` para runs de 1000+ perguntas.
- **`evaluation/`** — Pipeline de geração adversarial e avaliação LLM-as-a-Judge totalmente desacoplado do motor de consulta.
- **`cli.py`** — Ponto de entrada único. Toda orquestração via Typer.