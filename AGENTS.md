# Diretrizes de Desenvolvimento e Arquitetura (AGENTS.md)

Este documento estabelece as convenções de engenharia, arquitetura e padrões operacionais para desenvolvedores humanos e agentes de IA que operam neste repositório.

## 1. Visão do Projeto
`ragbench` é um framework e suíte de benchmarking para arquiteturas RAG (Retrieval-Augmented Generation), especializado em Knowledge Graph RAG (LightRAG) com inferência local via Ollama e avaliação analítica com LLM-as-a-Judge via RAGAS.

## 2. Princípios Arquiteturais
- **Ports & Adapters (Hexagonal Architecture):**
  - O domínio central (`core/`) e a orquestração de benchmarking não dependem diretamente de bibliotecas externas específicas. Motores de RAG (LightRAG, baselines) e provedores de LLM são desacoplados via interfaces/protocolos (`BaseRAGPipeline`, `BaseLLMClient`).
- **Resiliência e Tolerância a Falhas em Cargas Longas:**
  - Toda operação de lote massivo (1000+ consultas) deve ser idempotente, suportar *checkpointing* atômico e permitir `--resume`.
  - Tratamento defensivo de chamadas HTTP ao Ollama (retries com backoff exponencial para lidar com picos de VRAM/offload).
- **Tipagem Estrita e Contratos Pydantic:**
  - Todas as entradas/saídas de dados (POPs, perguntas sintéticas, respostas RAG, métricas de avaliação) são modeladas através de schemas Pydantic v2.
  - Não trafegar dicionários genéricos não tipados (`dict[str, Any]`) entre módulos.

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
- **Linting e Checagem Estática**:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  ```
- **Execução de Testes Unitários**:
  ```bash
  uv run pytest tests/
  ```
- **Execução do CLI**:
  ```bash
  uv run ragbench --help
  ```
