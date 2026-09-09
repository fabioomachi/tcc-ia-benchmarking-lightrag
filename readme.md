# TCC: IA Benchmarking - LightRAG

Ferramenta de benchmarking e avaliação de desempenho para arquiteturas RAG (Retrieval-Augmented Generation) com foco em LightRAG.

## 📌 Estrutura do Projeto

- `entradas/`: Datasets e arquivos de entrada para benchmark.
- `entradas/pops/`: arquivos de instruções para a llm.
- `entradas/perguntas/`: arquivos de lista de perguntas para testar a llm.
- `logs/`: logs da execução que servem como insumo para a RAGAS gerar as métricas.
- `resultados/`: Relatórios e relatórios de métricas gerados.
- `lightrag_ollama_db/`: Banco de grafo gerado pelo light rag.
- `src/`: Códigos-fonte da aplicação e scripts de avaliação.

## ⚙️ Infraestrutura de Modelos Locais (Ollama)

Este projeto utiliza o [Ollama](https://ollama.com/) para orquestrar a inferência de modelos locais, garantindo privacidade dos dados bancários (POPs) e reprodutibilidade do benchmark sem dependência de APIs externas.

### Topologia de Modelos

A arquitetura foi dividida em dois domínios para balancear o consumo de VRAM (restrito a 4GB + Offload para RAM) e a precisão analítica necessária para o LLM-as-a-Judge.

| Domínio | Papel | Modelo (Ollama) | Justificativa Arquitetural |
| :--- | :--- | :--- | :--- |
| **LightRAG (Engine)** | LLM Principal | `qwen2.5:3b` | Alta velocidade de geração e baixo footprint (cabe na VRAM), ideal para extração de grafos e consultas interativas em tempo real. |
| **LightRAG (Engine)** | Embeddings | `all-minilm` | Vetorização ágil e leve (384 dimensões). |
| **RAGAS (Evaluation)** | LLM Judge | `qwen2.5:7b` | Maior densidade paramétrica para raciocínio analítico. Essencial para avaliar métricas complexas como *Faithfulness* e *Answer Relevancy*. |
| **RAGAS (Evaluation)** | Embeddings Judge| `nomic-embed-text` | Capacidade nativa para janelas de contexto estendidas (até 8192 tokens). Previne estouro de limite (HTTP 500) ao processar o payload massivo do RAGAS para *Context Recall/Precision*. |

### Setup do Ambiente

Antes de iniciar os pipelines de indexação ou avaliação, é mandatório realizar o pull prévio dos artefatos para evitar timeouts durante a execução dos scripts.

Execute no terminal:

```bash
# Modelos do Motor de Busca (Indexação e RAG)
ollama pull qwen2.5:3b
ollama pull all-minilm

# Modelos do Framework de Avaliação (RAGAS)
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

## 🚀 Como Executar

1. **Clonar o repositório:**
```bash
git clone https://github.com/fabioomachi/tcc-ia-benchmarking-lightrag.git
cd tcc-ia-benchmarking-lightrag
```

2. **Criar e ativar o ambiente virtual:**
```bash
rm -rf venv
python3 -m venv .venv
source .venv/bin/activate
```

3. **Instalar dependências (via uv ou pip):**
```bash
# Recomendado (alta performance e isolamento moderno)
uv pip install -e ".[all]"

# Ou via pip padrão
pip install -r requirements.txt
pip install -e .
```

4. **Execução Moderna via CLI Unificada (`ragbench`):**
```bash
# 4.1. Validar conectividade com o Ollama
ragbench health

# 4.2. Indexar documentos POP no LightRAG
ragbench index

# 4.3. Gerar Golden Dataset adversarial (opcional)
ragbench generate-dataset --questions-per-doc 2

# 4.4. Executar benchmark em lote com checkpointing e resume automático
ragbench run --mode hybrid --concurrency 10

# 4.5. Executar avaliação LLM-as-a-Judge com RAGAS
ragbench eval

# 4.6. Sessão interativa no terminal (Streaming + Semantic Cache)
ragbench chat --mode hybrid
```

5. **Execução Legada (Scripts Procedurais):**
Caso deseje executar os scripts originais diretamente:
- Indexação: `python src/1_indexacao.py`
- Consultas / Lote: `python src/2_consulta.py`
- ETL de Logs: `python src/script_analisa_logs.py`
- Avaliação RAGAS: `python src/script_analisa_ragas.py`


## 🧠 Módulo de Consulta Avançada (`2_consulta.py`)

O pipeline de consulta foi arquitetado para suportar testes rigorosos de *benchmarking*, reduzindo latência de I/O e provendo observabilidade direta para as etapas de RAG e Geração.

### ⚙️ Parâmetros de CLI

Utilize os argumentos expostos para controlar a estratégia de recuperação, testar diferentes LLMs locais e injetar rotinas de testes massivos.

| Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `--mode` | `str` | `hybrid` | Estratégia de busca vetorial e em grafo do LightRAG (`naive`, `local`, `global`, `hybrid`). |
| `--top-k` | `int` | `5` | Número máximo de entidades e chunks documentais recuperados para composição do *prompt* final. |
| `--llm-model` | `str` | `qwen2.5:3b` | Identificador do modelo LLM servido via Ollama. |
| `--embed-model` | `str` | `all-minilm` | Identificador do modelo gerador de vetores de *embedding*. |
| `--embed-dim` | `int` | `384` | Dimensionalidade geométrica do vetor gerado pelo modelo de *embedding*. |
| `--ollama-url` | `str` | `http://localhost:11434/v1/` | Endpoint da API REST local (compatível com a especificação da OpenAI). |
| `--batch` | `str` | `None` | *Path* para arquivo `.txt` ou `.jsonl` contendo *queries* para *benchmarking*. Ativa o processamento em lote (*bypass* do modo interativo). |
| `--history-turns` | `int` | `3` | Tamanho da *Sliding Window* conversacional. Define quantos turnos passados são injetados no contexto atual. |
| `--cache-threshold`| `float`| `0.92` | Limiar de similaridade de cosseno ($0.0$ a $1.0$) para ocorrência de *hit* no *Semantic Cache*. |

### 🚀 Arquiteturas de Alta Performance Embutidas

*   **Semantic Caching (`O(1)` Retrieval):** *Short-circuit* no pipeline. Compara o *embedding* da requisição atual com consultas cacheadas em memória utilizando distância cosseno. Em caso de *hit* (acima do `--cache-threshold`), o fluxo bypassa o *traversal* de grafos e a inferência do LLM.
*   **Gestão de Contexto (Sliding Window):** Limita estritamente o histórico da sessão aos últimos $K$ turnos. Mitiga o efeito *Lost in the Middle* e evita o estouro do limite de tokens da janela de contexto de modelos menores.
*   **Telemetria Estruturada (APM Ready):** Injeção de decorators assíncronos que coletam a latência total de orquestração do RAG e o *Time To First Token* (TTFT) durante o *streaming*. Os logs são gerados em formato JSON encapsulado com a chave `METRIC_PAYLOAD:` para fácil *parsing* no stdout.

### 💻 Exemplos de Execução

**1. Interativo com Streaming e Cache (Padrão)**
O motor roda em tempo real aguardando inputs do terminal via I/O não-bloqueante.
```bash
python src/2_consulta.py
```
**2. Isolar Estratégia e Limitar Contexto**
Útil para medir a degradação de resposta caso o Retrieval devolva dados insuficientes ou muito espalhados na topologia do grafo.
```bash
python src/2_consulta.py --mode global --top-k 2
```

**3. Automação de Benchmarking (Processamento em Lote)**
Ao fornecer o parâmetro --batch, o streaming e a memória de sessão são desligados para garantir reproducibilidade entre testes isolados. Os resultados são parseados em um novo arquivo .jsonl.
```bash
python src/2_consulta.py --batch ./data/bateria_testes.jsonl --llm-model llama3:8b --mode
```

**4.  Modo Lote Automático (Lê todos os arquivos .txt ou .jsonl dentro de entradas/perguntas):**

```bash
python src/2_consulta.py --batch
```

**5. Modo Lote Customizado (Se quiser apontar para outro diretório específico opcionalmente):**

```bash
python src/2_consulta.py --batch outro_diretorio/customizado --concurrency 5
```