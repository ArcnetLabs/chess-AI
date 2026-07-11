"""
AI Model Provider Abstraction Layer.

Supports Ollama (local), OpenRouter, and OpenAI with automatic fallback.
All LLM access for the coach routes through this module.
"""
from __future__ import annotations

import asyncio
import json
import os
from time import perf_counter
from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI library not installed")

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx library not installed")

from ...core.config import settings


class ModelProvider(str, Enum):
    """Supported AI model providers."""

    OLLAMA = "ollama"
    LOCAL = "local"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    MOCK = "mock"


class AIClient:
    """Unified AI client with configurable provider fallback chain."""

    def __init__(
        self,
        provider: Optional[ModelProvider] = None,
        api_key: Optional[str] = None,
    ):
        self._forced_provider = provider
        self._api_key_override = api_key
        self._openrouter_client: Optional[httpx.AsyncClient] = None
        self.last_routing: Dict[str, Any] = {}
        logger.info("AI Client initialized (fallback chain enabled)")

    def _fallback_chain(self) -> List[str]:
        if self._forced_provider:
            return [self._forced_provider.value]
        runtime_mode = settings.LLM_RUNTIME_MODE.strip().lower()
        if runtime_mode == "development_tunnel":
            return [ModelProvider.OLLAMA.value]
        if runtime_mode != "production":
            raise ValueError(
                "LLM_RUNTIME_MODE must be 'development_tunnel' or 'production'"
            )
        primary = (settings.LLM_PRIMARY_PROVIDER or settings.MODEL_PROVIDER).strip().lower()
        configured = [
            part.strip().lower()
            for part in settings.LLM_FALLBACK_CHAIN.split(",")
            if part.strip()
        ]
        return list(dict.fromkeys(([primary] if primary else []) + configured))

    def _provider_timeout_seconds(self) -> float:
        """Give the development tunnel enough time for a local CPU model."""
        if settings.LLM_RUNTIME_MODE.strip().lower() == "development_tunnel":
            return max(settings.LLM_TIMEOUT_SECONDS, 75.0)
        return settings.LLM_TIMEOUT_SECONDS

    def _get_openrouter_client(self) -> httpx.AsyncClient:
        if self._openrouter_client is None:
            if not HTTPX_AVAILABLE:
                raise ImportError("httpx library required for OpenRouter")
            self._openrouter_client = httpx.AsyncClient(
                base_url="https://openrouter.ai/api/v1",
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://chess-insight-ai.com",
                    "X-Title": "Chess Insight AI",
                },
                timeout=self._provider_timeout_seconds(),
            )
        return self._openrouter_client

    def _ollama_request_headers(self) -> Dict[str, str]:
        """Load optional tunnel/auth headers without logging their values."""
        raw_headers = settings.OLLAMA_REQUEST_HEADERS_JSON.strip()
        if not raw_headers:
            return {}
        try:
            headers = json.loads(raw_headers)
        except json.JSONDecodeError as exc:
            raise ValueError("OLLAMA_REQUEST_HEADERS_JSON must be valid JSON") from exc
        if not isinstance(headers, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in headers.items()
        ):
            raise ValueError(
                "OLLAMA_REQUEST_HEADERS_JSON must be a JSON object of string headers"
            )
        return headers

    async def _ollama_health_check(self) -> bool:
        if not HTTPX_AVAILABLE:
            logger.warning("Ollama health check skipped because httpx is unavailable")
            return False
        base = settings.OLLAMA_BASE_URL.rstrip("/")
        try:
            async with httpx.AsyncClient(
                timeout=2.0, headers=self._ollama_request_headers()
            ) as client:
                response = await client.get(f"{base}/api/tags")
                if response.status_code != 200:
                    logger.warning(
                        "Ollama health check returned status {} for {} "
                        "(Cloudflare Access headers configured: {})",
                        response.status_code,
                        base,
                        bool(settings.OLLAMA_REQUEST_HEADERS_JSON.strip()),
                    )
                    return False
                return True
        except Exception as exc:
            logger.warning(
                "Ollama health check failed for {} (Cloudflare Access headers "
                "configured: {}): {}: {}",
                base,
                bool(settings.OLLAMA_REQUEST_HEADERS_JSON.strip()),
                type(exc).__name__,
                exc,
            )
            return False

    async def _local_health_check(self) -> bool:
        """Check a vLLM or other OpenAI-compatible local runtime."""
        if not HTTPX_AVAILABLE:
            return False
        base = settings.LLM_LOCAL_BASE_URL.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{base}/models")
                return response.status_code == 200
        except Exception as exc:
            logger.debug(f"Local OpenAI-compatible health check failed: {exc}")
            return False

    async def _with_retries(self, provider_name: str, operation):
        attempts = max(1, settings.LLM_MAX_RETRIES)
        last_error: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                return await operation()
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "{} request attempt {}/{} failed: {}: {}",
                    provider_name,
                    attempt + 1,
                    attempts,
                    type(exc).__name__,
                    str(exc) or repr(exc),
                )
                if attempt < attempts - 1:
                    await asyncio.sleep(0.25 * (attempt + 1))
        error_detail = str(last_error) or repr(last_error)
        raise RuntimeError(f"{provider_name} failed after {attempts} attempts: {error_detail}")

    def _record_routing(
        self,
        result: Dict[str, Any],
        errors: List[str],
        started_at: float,
    ) -> Dict[str, Any]:
        telemetry = {
            "provider": result.get("provider"),
            "model": result.get("model"),
            "fallback_used": bool(errors),
            "fallback_reason": "; ".join(errors) if errors else None,
            "latency_ms": round((perf_counter() - started_at) * 1000),
        }
        self.last_routing = telemetry
        return {**result, **telemetry}

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Single entry point — tries providers in fallback order."""
        return await self.chat_completion_with_fallback(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    async def chat_completion_with_fallback(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        errors: List[str] = []
        started_at = perf_counter()

        for provider_name in self._fallback_chain():
            if provider_name == ModelProvider.MOCK.value:
                if settings.ENVIRONMENT.lower() == "production":
                    errors.append("mock: disabled in production")
                    continue
                result = self._mock_chat(messages, model, temperature, max_tokens, **kwargs)
                return self._record_routing(result, errors, started_at)

            if provider_name == ModelProvider.LOCAL.value:
                if not await self._local_health_check():
                    errors.append("local: unavailable")
                    continue
                try:
                    result = await self._with_retries(
                        "local",
                        lambda: self._local_openai_chat(
                            messages, model, temperature, max_tokens, **kwargs
                        ),
                    )
                    logger.info("LLM response via local OpenAI-compatible runtime")
                    return self._record_routing(result, errors, started_at)
                except Exception as exc:
                    errors.append(f"local: {exc}")
                    continue

            if provider_name == ModelProvider.OLLAMA.value:
                if not await self._ollama_health_check():
                    errors.append("ollama: unavailable")
                    continue
                try:
                    result = await self._with_retries(
                        "ollama",
                        lambda: self._ollama_chat(
                            messages, model, temperature, max_tokens, **kwargs
                        ),
                    )
                    logger.info("LLM response via ollama")
                    return self._record_routing(result, errors, started_at)
                except Exception as exc:
                    errors.append(f"ollama: {exc}")
                    continue

            if provider_name == ModelProvider.OPENROUTER.value:
                if not settings.OPENROUTER_API_KEY:
                    errors.append("openrouter: missing API key")
                    continue
                try:
                    result = await self._with_retries(
                        "openrouter",
                        lambda: self._openrouter_chat(
                            messages, model, temperature, max_tokens, **kwargs
                        ),
                    )
                    logger.info("LLM response via openrouter")
                    return self._record_routing(result, errors, started_at)
                except Exception as exc:
                    errors.append(f"openrouter: {exc}")
                    continue

            if provider_name == ModelProvider.OPENAI.value:
                if not settings.OPENAI_API_KEY:
                    errors.append("openai: missing API key")
                    continue
                try:
                    result = await self._with_retries(
                        "openai",
                        lambda: self._openai_chat(
                            messages, model, temperature, max_tokens, **kwargs
                        ),
                    )
                    logger.info("LLM response via openai")
                    return self._record_routing(result, errors, started_at)
                except Exception as exc:
                    errors.append(f"openai: {exc}")
                    continue

            errors.append(f"{provider_name}: unsupported provider")

        raise RuntimeError(f"All LLM providers failed: {'; '.join(errors)}")

    async def _local_openai_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Call a local OpenAI-compatible runtime such as vLLM."""
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx required for local OpenAI-compatible runtime")

        model_name = model or settings.LLM_LOCAL_MODEL
        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        headers = {}
        if settings.LLM_LOCAL_API_KEY:
            headers["Authorization"] = f"Bearer {settings.LLM_LOCAL_API_KEY}"

        base = settings.LLM_LOCAL_BASE_URL.rstrip("/")
        async with httpx.AsyncClient(
            timeout=self._provider_timeout_seconds(), headers=headers
        ) as client:
            response = await client.post(f"{base}/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

        return {
            "content": data["choices"][0]["message"]["content"],
            "usage": data.get("usage", {}),
            "model": data.get("model", model_name),
            "provider": "local",
        }

    async def _ollama_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx required for Ollama")

        base = settings.OLLAMA_BASE_URL.rstrip("/")
        payload: Dict[str, Any] = {
            "model": model or settings.OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        payload.update(kwargs)

        async with httpx.AsyncClient(
            timeout=self._provider_timeout_seconds(),
            headers=self._ollama_request_headers(),
        ) as client:
            response = await client.post(f"{base}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

        content = (data.get("message") or {}).get("content") or ""
        return {
            "content": content,
            "usage": {},
            "model": data.get("model", payload["model"]),
            "provider": "ollama",
        }

    async def _openai_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if not OPENAI_AVAILABLE:
            raise ImportError("openai library not installed")

        openai.api_key = self._api_key_override or settings.OPENAI_API_KEY
        model_name = model or settings.OPENAI_MODEL

        response = await openai.ChatCompletion.acreate(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        return {
            "content": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            "model": response.model,
            "provider": "openai",
        }

    async def _openrouter_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        model_name = model or settings.OPENROUTER_MODEL
        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        client = self._get_openrouter_client()
        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        return {
            "content": data["choices"][0]["message"]["content"],
            "usage": data.get("usage", {}),
            "model": data.get("model", model_name),
            "provider": "openrouter",
        }

    def _mock_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        last_message = messages[-1]["content"] if messages else ""
        return {
            "content": f"Mock response to: {last_message[:50]}...",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "model": model or "mock-model",
            "provider": "mock",
        }

    async def close(self) -> None:
        if self._openrouter_client is not None:
            await self._openrouter_client.aclose()
            self._openrouter_client = None


_ai_client: Optional[AIClient] = None


def get_ai_client() -> AIClient:
    """Get or create AI client singleton."""
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client


async def close_ai_client() -> None:
    """Close AI client connections."""
    global _ai_client
    if _ai_client:
        await _ai_client.close()
        _ai_client = None
