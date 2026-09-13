import asyncio
import httpx
from ragbench.config import settings

async def test_new_embedding():
    api_key = settings.ollama.api_key
    modelo = "gemini-embedding-001"
    
    print(f"Testando API REST com o novo modelo: {modelo}")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:embedContent?key={api_key}"
    
    payload = {
        "content": {
            "parts": [{"text": "Validando o novo motor de embeddings do Gemini."}]
        },
        "outputDimensionality": 768  # Reduz os 3072 vetores nativos para os 768 exigidos
    }
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                vetor = response.json().get("embedding", {}).get("values", [])
                print(f"✅ SUCESSO! O endpoint nativo respondeu.")
                print(f"   Tamanho do vetor: {len(vetor)} dimensões")
                print(f"   Amostra: {vetor[:3]} ...")
            else:
                print(f"❌ Falha: HTTP {response.status_code}")
                print(f"   Detalhes: {response.text.strip()}")
        except Exception as e:
            print(f"❌ Erro de conexão: {e}")

if __name__ == "__main__":
    asyncio.run(test_new_embedding())