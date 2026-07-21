"""
Single entry point for all LLM calls in the app.

Why this exists: every agent needs to call a model, and the model backend
changes depending on where we're running (Ollama locally, vLLM on the pod).
No agent code should ever import httpx or know about Ollama/vLLM directly —
they call `llm_client.generate(...)` and this module handles the rest.

This is also where we capture the numbers that go in proofs/ later:
latency, time-to-first-token (streaming only), and token counts, so
benchmarking doesn't require bolting on separate instrumentation afterward.
"""

import time
from dataclasses import dataclass
from typing import Literal

import httpx

from app.core.config import settings

ModelSize = Literal["small", "large"]


@dataclass
class GenerationResult:
    text: str
    model: str
    latency_seconds: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    @property
    def tokens_per_second(self) -> float | None:
        if self.completion_tokens and self.latency_seconds > 0:
            return round(self.completion_tokens / self.latency_seconds, 2)
        return None


class LLMClient:
    def __init__(self) -> None:
        self.backend = settings.llm_backend
        self._client = httpx.AsyncClient(timeout=300.0)

    def _model_name(self, size: ModelSize) -> str:
        if self.backend == "vllm":
            return settings.vllm_small_model if size == "small" else settings.vllm_large_model
        return settings.ollama_small_model if size == "small" else settings.ollama_large_model

    def _vllm_base_url(self, size: ModelSize) -> str:
        if size == "large":
            return settings.vllm_large_base_url
        return settings.vllm_base_url

    async def generate(
        self,
        prompt: str,
        size: ModelSize = "small",
        system: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> GenerationResult:
        model = self._model_name(size)
        start = time.perf_counter()

        if self.backend == "vllm":
            result = await self._generate_vllm(model, prompt, system, temperature, max_tokens, size)
        else:
            result = await self._generate_ollama(model, prompt, system, temperature, max_tokens)

        elapsed = time.perf_counter() - start
        result.latency_seconds = elapsed
        return result

    async def _generate_ollama(
        self, model: str, prompt: str, system: str | None, temperature: float, max_tokens: int
    ) -> GenerationResult:
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system or "",
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        resp = await self._client.post(f"{settings.ollama_base_url}/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return GenerationResult(
            text=data.get("response", ""),
            model=model,
            latency_seconds=0.0,  # filled in by caller
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
        )

    async def embed(self, text: str) -> list[float]:
        """Embeddings only make sense against Ollama's local embedding model
        for now — vLLM embedding routing can be added later if needed."""
        resp = await self._client.post(
            f"{settings.ollama_base_url}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text},
        )
        resp.raise_for_status()
        return resp.json()["embedding"]

    async def _generate_vllm(
        self, model: str, prompt: str, system: str | None, temperature: float, max_tokens: int,
        size: ModelSize = "small",
    ) -> GenerationResult:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Authorization": f"Bearer {settings.vllm_api_key}"}
        base_url = self._vllm_base_url(size)
        resp = await self._client.post(
            f"{base_url}/chat/completions", json=payload, headers=headers
        )
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        return GenerationResult(
            text=data["choices"][0]["message"]["content"],
            model=model,
            latency_seconds=0.0,  # filled in by caller
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )

    async def close(self) -> None:
        await self._client.aclose()


llm_client = LLMClient()