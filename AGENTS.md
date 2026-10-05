# Diretrizes de Desenvolvimento e Arquitetura (AGENTS.md)

Este documento estabelece as convenções de engenharia, arquitetura e padrões operacionais para desenvolvedores humanos e agentes de IA que operam neste repositório.

## 1. Visão do Projeto
`ragbench` é um framework e suíte de benchmarking para arquiteturas RAG (Retrieval-Augmented Generation), especializado em Knowledge Graph RAG (LightRAG) com transporte unificado via API Gemini (OpenAI-compatível) e avaliação analítica com LLM-as-a-Judge via RAGAS. Ollama local é mantido apenas como fallback de `health`.

## 2. Princípios Arquiteturais
- **Ports & Adapters (Hexagonal Architecture):**
  - O domínio central (`core/`) e a orquestração de benchmarking não dependem diretamente de bibliotecas externas específicas. Motores de RAG (LightRAG, baselines) e provedores de LLM são desacoplados via interfaces/protocolos (`BaseRAGPipeline`, `BaseCache`, `BaseExecutionStorage` — todos `runtime_checkable`; engines herdam `BaseRAGPipeline` explicitamente).
- **Resiliência e Tolerância a Falhas em Cargas Longas:**
  - Toda operação de lote massivo (1000+ consultas) deve ser idempotente, suportar *checkpointing* atômico em SQLite (WAL + `timeout=30`) e permitir `--resume`.
  - Transporte resiliente (`ResilientOllamaClient`): rate-limit 4.2s + retries com backoff/jitter; `QuotaExhaustedError` (exit 3) com parada graciosa em 429/503 do Gemini; index incremental por SHA256 (`IndexManifest`); embeddings sem zeros silenciosos (falha levanta, runner faz bypass de cache).
  - Avaliação RAGAS: juiz dedicado (`RAGAS__JUDGE_MODEL`), `AnswerRelevancy(strictness=1)` no Gemini, `GeminiRestEmbeddings` via REST `:embedContent` (endpoint OpenAI-compatível retorna 501), `RunConfig(max_retries=15, max_wait=180)`.
- **Tipagem Estrita e Contratos Pydantic:**
  - Todas as entradas/saídas de dados (POPs, perguntas sintéticas, respostas RAG, métricas de avaliação) são modeladas através de schemas Pydantic v2 (`RouteInfo`, `CachedItem`, `RunManifest.config` tipado, validators `ge/le` em latências/similaridade/top_k, `EngineRole = Literal["index","chat"]`).
  - Não trafegar dicionários genéricos não tipados (`dict[str, Any]`) entre módulos (`RouteInfo` oferece acesso dict-like só por compatibilidade legada).
  - Segredos como `SecretStr` com scrub em logs (`SecretScrubFilter`) + `config-check` sem vazar chave.

## 3. Padrões de Código & Estilo
- **Python 3.11+ / 3.12**: Utilizar recursos modernos de tipagem (`list[str]`, `str | None`, `TypeVar`, `Protocol`).
- **I/O Assíncrono (`asyncio`)**:
  - Toda operação de rede ou inferência de LLM é estritamente assíncrona (`async`/`await`).
  - Operações bloqueantes de CPU ou I/O de disco pesado devem usar `asyncio.to_thread` se necessário.
  - Concorrência deve ser sempre balizada por `asyncio.Semaphore` para respeitar os limites de memória GPU/RAM.
- **Formatação e Linting**:
  - `ruff format` e `ruff check` (comprimento máximo de linha: 100 caracteres).
- **Sem Estado Global**:
  - Evitar variáveis globais mutáveis. Utilizar injeção de dependência via classes ou instâncias de configuração (`BenchmarkSettings`).

## 4. Comandos de Validação e Execução
- **Sincronização de Dependências**:
  ```bash
  uv pip install -e ".[all]"
  ```
- **Pré-voo (antes de index/run/eval)**:
  ```bash
  uv run ragbench health
  uv run ragbench config-check
  ```
- **Linting e Checagem Estática**:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  ```
- **Execução de Testes (gate de cobertura: 80%)**:
  ```bash
  uv run pytest tests/
  ```
- **Execução do CLI**:
  ```bash
  uv run ragbench --help
  uv run ragbench run-clarify --help
  ```
- **Regeneração de relatório**: seguir `relatorio-tcc/PROMPT-regenerar-relatorio.md` (só leitura de `runs/`; nunca editar `src/` nesse fluxo).

## 5. Débitos Técnicos Conhecidos
- `engines/decision_tree_engine.py` (~1100L, 8 ramos POP): monolito intencional no TCC; quebrar em `tree/<pop>.py` + tabela `BRANCHES` quando houver fôlego (cobertura `test_tree.py` ~60 ramos deve continuar verde).
- `cli_commands/` ainda concentra lógica de batch/roteamento/manifest; extrair `BatchExecutor` único (`run`, `run-direct`, `run-clarify`, `run-tree`) quando possível.
- Roteador só-grafo tem estratégias tunadas para 2 docs (`local/k10` acesso, `hybrid/k5` CDC); demais POPs usam fallback `hybrid/k5` — tunar por POP exige probes dedicados.
