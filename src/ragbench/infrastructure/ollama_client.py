import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import numpy as np
from openai import AsyncOpenAI

from ragbench.config import OllamaSettings
from ragbench.core.exceptions import OllamaConnectionError

logger = logging.getLogger("ragbench.ollama")


class ResilientOllamaClient:
    """Cliente assíncrono para inferência e embeddings no Ollama com resiliência a falhas."""

    def __init__(self, settings: OllamaSettings):
        self.settings = settings
        self.client = AsyncOpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            timeout=httpx.Timeout(settings.request_timeout, connect=10.0),
            max_retries=settings.max_retries,
        )

    async def check_health(self) -> bool:
        """Verifica se a instância local do Ollama está respondendo."""
        try:
            # Testa endpoint básico de modelos
            async with httpx.AsyncClient(timeout=5.0) as http_client:
                health_url = self.settings.base_url.replace("/v1/", "") + "/api/tags"
                response = await http_client.get(health_url)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Falha ao conectar ao Ollama ({self.settings.base_url}): {e}")
            return False

    async def generate_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        stream: bool = False,
        **kwargs: Any,
    ) -> str | AsyncGenerator[str, None]:
        """Gera resposta via chat completions com retries e backoff exponencial."""
        valid_kwargs = {
            k: v for k, v in kwargs.items() if k in ["max_tokens", "top_p", "response_format"]
        }

        max_attempts = 3
        backoff = 1.5

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    stream=stream,
                    **valid_kwargs,
                )

                if stream:

                    async def stream_generator(stream_resp=response):
                        async for chunk in stream_resp:
                            content = chunk.choices[0].delta.content
                            if content:
                                yield content

                    return stream_generator()
                else:
                    return response.choices[0].message.content or ""

            except Exception as e:
                logger.warning(
                    f"Tentativa {attempt}/{max_attempts} de completion falhou no modelo {model}: {e}"
                )
                if attempt == max_attempts:
                    raise OllamaConnectionError(
                        f"Esgotadas tentativas de completion no Ollama ({model}): {e}"
                    ) from e
                await asyncio.sleep(backoff * attempt)

        return ""

    async def get_embeddings(self, model: str, texts: list[str]) -> np.ndarray:
        """Gera vetores de embedding para uma lista de textos."""
        max_attempts = 3
        backoff = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self.client.embeddings.create(model=model, input=texts)
                return np.array([res.embedding for res in response.data])
            except Exception as e:
                logger.warning(f"Tentativa {attempt}/{max_attempts} de embeddings falhou: {e}")
                if attempt == max_attempts:
                    raise OllamaConnectionError(
                        f"Esgotadas tentativas de embedding no Ollama ({model}): {e}"
                    ) from e
                await asyncio.sleep(backoff * attempt)

        return np.array([])
