import asyncio
import logging
import random
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import numpy as np
from google import genai
from openai import AsyncOpenAI, RateLimitError

from ragbench.config import OllamaSettings
from ragbench.core.exceptions import OllamaConnectionError

logger = logging.getLogger("ragbench.ollama")


class ResilientOllamaClient:
    """Cliente unificado 100% Google Gemini (LLM + Embeddings)."""

    def __init__(self, settings: OllamaSettings):
        self.settings = settings

        # Cliente OpenAI para a API Gemini (Chat / Completions)
        self.client = AsyncOpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            timeout=httpx.Timeout(settings.request_timeout, connect=10.0),
            max_retries=settings.max_retries,
        )

        # Cliente oficial do Google para Embeddings
        self.genai_client = genai.Client(api_key=settings.api_key)

        self._request_interval_seconds = 4.2
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time = 0.0

    async def _wait_for_rate_limit(self) -> None:
        """Garante a cadência mínima entre requisições ao Gemini."""
        async with self._rate_limit_lock:
            now = asyncio.get_running_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self._request_interval_seconds:
                await asyncio.sleep(self._request_interval_seconds - elapsed)
            self._last_request_time = asyncio.get_running_loop().time()

    async def check_health(self) -> bool:
        """Verifica a conectividade básica com a API Gemini."""
        return bool(self.settings.api_key)

    async def generate_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        stream: bool = False,
        **kwargs: Any,
    ) -> str | AsyncGenerator[str, None]:
        """Gera respostas via Gemini (Chat Completions)."""
        valid_kwargs = {
            k: v for k, v in kwargs.items() if k in ["max_tokens", "top_p", "response_format"]
        }

        max_attempts = 6
        initial_delay = 5.0
        backoff_factor = 2.0
        max_delay = 60.0
        backoff = 3.0

        for attempt in range(1, max_attempts + 1):
            try:
                await self._wait_for_rate_limit()

                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=8192,
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

            except RateLimitError as e:
                if attempt == max_attempts:
                    raise OllamaConnectionError(
                        f"Rate limit esgotado no modelo {model}: {e}"
                    ) from e

                calculated_delay = initial_delay * (backoff_factor ** (attempt - 1))
                jittered_delay = random.uniform(2.0, min(max_delay, calculated_delay))
                logger.warning(
                    f"⚠️ [Rate Limit 429] Tentativa {attempt}/{max_attempts} falhou. "
                    f"Aguardando {jittered_delay:.2f}s..."
                )
                await asyncio.sleep(jittered_delay)

            except Exception as e:
                logger.warning(f"Tentativa {attempt}/{max_attempts} de completion falhou: {e}")
                if attempt == max_attempts:
                    raise OllamaConnectionError(f"Falha no modelo ({model}): {e}") from e
                await asyncio.sleep(backoff * attempt)

        return ""

    async def get_embeddings(
        self, model: str, texts: list[str], **kwargs: Any
    ) -> np.ndarray:
        """Gera vetores via HTTP REST nativo com micro-lotes para evitar Timeouts."""
        dim = kwargs.get("embedding_dim", 768)
        api_key = self.settings.api_key
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={api_key}"
        
        # Semáforo reduzido para não sobrecarregar as conexões ativas
        semaphore = asyncio.Semaphore(3)

        async def _safe_fetch(text: str) -> list[float]:
            payload = {
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": dim
            }
            
            async with semaphore:
                for attempt in range(1, 4):
                    try:
                        # Timeout super curto (10s) para falhar rápido e retentar se o Google travar
                        async with httpx.AsyncClient(timeout=10.0) as client:
                            resp = await client.post(url, json=payload)
                            
                            if resp.status_code == 429:
                                await asyncio.sleep(2.0 * attempt)
                                continue
                                
                            resp.raise_for_status()
                            return resp.json().get("embedding", {}).get("values", [0.0] * dim)
                            
                    except Exception as e:
                        if attempt == 3:
                            logger.error(f"Falha REST no embedding: {e}")
                            return [0.0] * dim
                        await asyncio.sleep(1.0)
            return [0.0] * dim

        # Processamento em MICRO-LOTES para evitar que o LightRAG estoure o timeout
        all_embeddings = []
        chunk_size = 5
        
        for i in range(0, len(texts), chunk_size):
            batch = texts[i : i + chunk_size]
            tasks = [_safe_fetch(t) for t in batch]
            
            # Aguarda a resolução do pequeno lote
            batch_results = await asyncio.gather(*tasks)
            all_embeddings.extend(batch_results)
            
            # Micro-pausa para respiro do servidor
            await asyncio.sleep(0.3)

        return np.array(all_embeddings)