import asyncio

import httpx

from ragbench.config import settings


async def test_new_embedding():
    api_key = settings.ollama.api_key.get_secret_value()
    modelo = "gemini-embedding-001"

    print(f"Testando API REST com o novo modelo: {modelo}")

    # A chave viaja em header, nunca na URL (URLs vazam em tracebacks e logs).
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:embedContent"
    headers = {"x-goog-api-key": api_key}

    payload = {
        "content": {"parts": [{"text": "Validando o novo motor de embeddings do Gemini."}]},
        "outputDimensionality": 768,  # Reduz os 3072 vetores nativos para os 768 exigidos
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                vetor = response.json().get("embedding", {}).get("values", [])
                print("✅ SUCESSO! O endpoint nativo respondeu.")
                print(f"   Tamanho do vetor: {len(vetor)} dimensões")
                print(f"   Amostra: {vetor[:3]} ...")
            else:
                print(f"❌ Falha: HTTP {response.status_code}")
        except Exception:
            print("❌ Erro de conexão (detalhes suprimidos para não expor credenciais)")


if __name__ == "__main__":
    asyncio.run(test_new_embedding())
