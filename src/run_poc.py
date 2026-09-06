import os
import asyncio
import numpy as np
from pathlib import Path
from openai import AsyncOpenAI
from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc

# Resolução robusta de caminhos absolutos
BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "input"
WORKING_DIR = BASE_DIR / "lightrag_ollama_db"

INPUT_DIR.mkdir(parents=True, exist_ok=True)
WORKING_DIR.mkdir(parents=True, exist_ok=True)

client = AsyncOpenAI(
    base_url="http://localhost:11434/v1/",
    api_key="ollama_local"
)

async def custom_llm_func(prompt, system_prompt=None, history_messages=[], **kwargs):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history_messages:
        messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})

    valid_kwargs = {k: v for k, v in kwargs.items() if k in ["temperature", "max_tokens", "top_p"]}

    response = await client.chat.completions.create(
        model="qwen2.5:3b",
        messages=messages,
        **valid_kwargs
    )
    return response.choices[0].message.content

async def custom_embedding_func(texts: list[str]) -> np.ndarray:
    response = await client.embeddings.create(
        model="all-minilm",
        input=texts
    )
    embeddings = [res.embedding for res in response.data]
    return np.array(embeddings)

async def main():
    rag = LightRAG(
        working_dir=str(WORKING_DIR),
        llm_model_func=custom_llm_func,
        embedding_func=EmbeddingFunc(
            embedding_dim=384,
            max_token_size=8192,
            func=custom_embedding_func
        )
    )

    # ---------------------------------------------------------
    # CORREÇÃO: Inicialização explícita do pipeline e storages
    # ---------------------------------------------------------
    await rag.initialize_storages()

    pop_path = INPUT_DIR / "pop_cancelamento_pix.txt"
    if not pop_path.exists():
        conteudo_sintetico = (
            "PROCEDIMENTO OPERACIONAL PADRÃO - POP-014: Cancelamento de PIX por Suspeita de Fraude. "
            "1. O operador deve validar a identidade do cliente via biometria facial. "
            "2. Caso haja contestação por golpe do falso leilão, o bloqueio cautelar deve ser acionado no sistema BACEN em até 30 minutos. "
            "3. É estritamente proibido o estorno manual sem a autorização da mesa de compliance."
        )
        pop_path.write_text(conteudo_sintetico, encoding="utf-8")
        print("Arquivo POP sintético gerado automaticamente.")

    print("Iniciando indexação... (Isso pode levar alguns minutos na GTX 1650)")
    await rag.ainsert(pop_path.read_text(encoding="utf-8"))
    print("Indexação concluída com sucesso!")

    query = "Qual é o procedimento obrigatório para cancelamento de PIX sob suspeita de fraude segundo a norma BACEN?"
    
    response = await rag.aquery(
        query, 
        param=QueryParam(mode="hybrid")
    )

    print("\n--- Resposta Gerada ---")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())