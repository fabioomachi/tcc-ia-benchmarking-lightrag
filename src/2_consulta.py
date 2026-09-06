import asyncio
import numpy as np
from pathlib import Path
from openai import AsyncOpenAI
from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc

# 1. Configuração de Caminhos
BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).parent.name == "src" else Path(__file__).resolve().parent
WORKING_DIR = BASE_DIR / "lightrag_ollama_db"

if not WORKING_DIR.exists():
    raise FileNotFoundError("Banco de grafos não encontrado. Execute '1_indexacao.py' primeiro.")

# 2. Wrappers de Comunicação com Ollama Local
client = AsyncOpenAI(base_url="http://localhost:11434/v1/", api_key="ollama_local")

async def custom_llm_func(prompt, system_prompt=None, history_messages=[], **kwargs):
    messages = []
    if system_prompt: messages.append({"role": "system", "content": system_prompt})
    if history_messages: messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})
    valid_kwargs = {k: v for k, v in kwargs.items() if k in ["temperature", "max_tokens", "top_p"]}
    
    response = await client.chat.completions.create(model="qwen2.5:3b", messages=messages, **valid_kwargs)
    return response.choices[0].message.content

async def custom_embedding_func(texts: list[str]) -> np.ndarray:
    response = await client.embeddings.create(model="all-minilm", input=texts)
    return np.array([res.embedding for res in response.data])

async def main():
    print("Carregando Grafo de Conhecimento...")
    rag = LightRAG(
        working_dir=str(WORKING_DIR),
        llm_model_func=custom_llm_func,
        embedding_func=EmbeddingFunc(embedding_dim=384, max_token_size=8192, func=custom_embedding_func)
    )
    await rag.initialize_storages()
    print("✅ Motor de Consulta Operacional!\n")

    # Loop Interativo de Consultas
    while True:
        query = input("Digite sua pergunta (ou 'sair' para encerrar): \n> ")
        if query.lower() in ['sair', 'exit', 'quit']:
            break
        
        print("\nProcessando (Hybrid Search)...")
        response = await rag.aquery(query, param=QueryParam(mode="hybrid"))
        print("\n--- Resposta Gerada ---")
        print(response)
        print("-" * 40 + "\n")

if __name__ == "__main__":
    asyncio.run(main())