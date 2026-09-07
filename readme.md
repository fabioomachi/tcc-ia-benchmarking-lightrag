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

3. **Instalar dependências:**
```bash
pip install -r requirements.txt
```

4. **Executar o benchmark:**
4.1. Certifique-se de que o Ollama está rodando (ollama serve).
4.2. Execute a indexação: python src/1_indexacao.py
4.3. Após o término, inicie o motor de perguntas: python src/2_consulta.py


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