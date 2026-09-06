# TCC: IA Benchmarking - LightRAG

Ferramenta de benchmarking e avaliação de desempenho para arquiteturas RAG (Retrieval-Augmented Generation) com foco em LightRAG.

## 📌 Estrutura do Projeto

- `data/`: Datasets e arquivos de entrada para benchmark.
- `results/`: Relatórios e relatórios de métricas gerados.
- `src/`: Códigos-fonte da aplicação e scripts de avaliação.

## 🚀 Como Executar

1. **Clonar o repositório:**
bash
git clone https://github.com/fabioomachi/tcc-ia-benchmarking-lightrag.git
cd tcc-ia-benchmarking-lightrag


2. **Criar e ativar o ambiente virtual:**
bash
python3 -m venv .venv
source .venv/bin/activate


3. **Instalar dependências:**
bash
pip install -r requirements.txt


4. **Executar o benchmark:**
4.1. Certifique-se de que o Ollama está rodando (ollama serve).
4.2. Execute a indexação: src/python 1_indexacao.py
4.3. Após o término, inicie o motor de perguntas: python src/2_consulta.py