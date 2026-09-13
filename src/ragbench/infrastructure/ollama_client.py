import asyncio
import logging
import random
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import numpy as np
from google import genai
from openai import AsyncOpenAI, RateLimitError

from ragbench.config import ChatSettings, OllamaSettings
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
            timeout=httpx.Timeout(settings.request_timeout, connect=settings.connect_timeout),
            max_retries=settings.max_retries,
        )

        # Cliente oficial do Google para Embeddings
        self.genai_client = genai.Client(api_key=settings.api_key)

        self._request_interval_seconds = settings.rate_limit_interval_seconds
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
        temperature: float | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> str | AsyncGenerator[str, None]:
        """Gera respostas via Gemini (Chat Completions)."""
        effective_temperature = kwargs.pop(
            "temperature",
            self.settings.completion_default_temperature if temperature is None else temperature,
        )
        effective_max_tokens = kwargs.pop("max_tokens", self.settings.completion_max_tokens)
        valid_kwargs = {k: v for k, v in kwargs.items() if k in ["top_p", "response_format"]}
        max_attempts = self.settings.completion_max_attempts
        initial_delay = self.settings.retry_initial_delay
        backoff_factor = self.settings.retry_backoff_factor
        max_delay = self.settings.retry_max_delay
        backoff = self.settings.retry_backoff

        for attempt in range(1, max_attempts + 1):
            try:
                await self._wait_for_rate_limit()

                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=effective_temperature,
                    max_tokens=effective_max_tokens,
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
                jittered_delay = random.uniform(
                    self.settings.retry_jitter_min, min(max_delay, calculated_delay)
                )
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

    async def get_embeddings(self, model: str, texts: list[str], **kwargs: Any) -> np.ndarray:
        """Gera vetores via HTTP REST nativo com micro-lotes para evitar Timeouts."""
        dim = kwargs.get("embedding_dim", self.settings.embedding_default_dim)
        api_key = self.settings.api_key

        url = (
            f"{self.settings.embedding_api_base_url.rstrip('/')}"
            f"/{self.settings.embedding_api_model}:embedContent"
        )
        headers = {"x-goog-api-key": api_key}

        # Semáforo reduzido para não sobrecarregar as conexões ativas
        semaphore = asyncio.Semaphore(self.settings.embedding_max_concurrency)

        async def _safe_fetch(text: str) -> list[float]:
            payload = {"content": {"parts": [{"text": text}]}, "outputDimensionality": dim}

            async with semaphore:
                for attempt in range(1, self.settings.embedding_max_attempts + 1):
                    try:
                        # Timeout super curto (10s) para falhar rápido e retentar se o Google travar
                        async with httpx.AsyncClient(
                            timeout=self.settings.embedding_timeout
                        ) as client:
                            resp = await client.post(url, json=payload, headers=headers)

                            if resp.status_code == 429:
                                await asyncio.sleep(self.settings.embedding_retry_delay * attempt)
                                continue

                            resp.raise_for_status()
                            return resp.json().get("embedding", {}).get("values", [0.0] * dim)

                    except Exception as e:
                        if attempt == self.settings.embedding_max_attempts:
                            logger.error(f"Falha REST no embedding: {e}")
                            return [0.0] * dim
                        await asyncio.sleep(self.settings.embedding_retry_short_delay)
            return [0.0] * dim

        # Processamento em MICRO-LOTES para evitar que o LightRAG estoure o timeout
        all_embeddings = []
        chunk_size = self.settings.embedding_batch_size

        for i in range(0, len(texts), chunk_size):
            batch = texts[i : i + chunk_size]
            tasks = [_safe_fetch(t) for t in batch]

            # Aguarda a resolução do pequeno lote
            batch_results = await asyncio.gather(*tasks)
            all_embeddings.extend(batch_results)

            # Micro-pausa para respiro do servidor
            await asyncio.sleep(self.settings.embedding_micro_pause)

        return np.array(all_embeddings)


class OllamaChatClient:
    """Cliente Ollama local para chat/query (ex: qwen3.5:4b + all-minilm).

    Sem lógica Gemini (sem rate-limit agressivo, sem REST de embeddings
    do Google). Usa a API OpenAI-compatível do Ollama local.
    """

    def __init__(self, settings: ChatSettings):
        self.settings = settings
        self.client = AsyncOpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            timeout=httpx.Timeout(settings.request_timeout, connect=settings.connect_timeout),
            max_retries=settings.max_retries,
        )

    async def check_health(self) -> bool:
        """Verifica a conectividade com o Ollama local."""
        try:
            await self.client.models.list()
            return True
        except Exception as e:
            logger.warning(f"Ollama local indisponível: {e}")
            return False

    async def generate_completion(
        self,
        model: str | None = None,
        messages: list[dict[str, str]] | None = None,
        temperature: float | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> str | AsyncGenerator[str, None]:
        """Gera respostas via Ollama local."""
        effective_model = model or self.settings.llm_model
        effective_temperature = self.settings.temperature if temperature is None else temperature
        effective_max_tokens = kwargs.pop("max_tokens", self.settings.max_tokens)
        valid_kwargs = {k: v for k, v in kwargs.items() if k in ["top_p", "response_format"]}

        response = await self.client.chat.completions.create(
            model=effective_model,
            messages=messages or [],
            temperature=effective_temperature,
            max_tokens=effective_max_tokens,
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
        return response.choices[0].message.content or ""

    async def get_embeddings(
        self, model: str | None = None, texts: list[str] | None = None, **kwargs: Any
    ) -> np.ndarray:
        """Gera embeddings via Ollama local (/api/embed)."""
        effective_model = model or self.settings.embed_model
        dim = kwargs.get("embedding_dim", self.settings.embed_dim)
        payload_texts = texts or []

        base = self.settings.base_url.rstrip("/").removesuffix("/v1")
        url = f"{base}/api/embed"
        timeout = httpx.Timeout(self.settings.request_timeout)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json={"model": effective_model, "input": payload_texts})
            resp.raise_for_status()
            data = resp.json().get("embeddings", [])

        if not data:
            return np.zeros((len(payload_texts), dim))
        arr = np.array(data)
        if arr.shape[1] != dim:
            logger.warning(f"Dimensão do embedding ({arr.shape[1]}) difere do configurado ({dim})")
        return arr
