"""Tests for AI client provider fallback."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.integration.ai_client import AIClient, ModelProvider


def _make_async_client_mock(*, get_response=None, post_response=None, side_effects=None):
    """Build a mock httpx.AsyncClient context manager."""
    mock_client = AsyncMock()

    if side_effects:
        mock_client.get = AsyncMock(side_effect=side_effects.get("get"))
        mock_client.post = AsyncMock(side_effect=side_effects.get("post"))
    else:
        if get_response is not None:
            mock_client.get = AsyncMock(return_value=get_response)
        if post_response is not None:
            mock_client.post = AsyncMock(return_value=post_response)

    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def test_development_tunnel_mode_only_routes_to_ollama(monkeypatch):
    monkeypatch.setattr(
        "app.services.integration.ai_client.settings.LLM_RUNTIME_MODE",
        "development_tunnel",
    )
    monkeypatch.setattr(
        "app.services.integration.ai_client.settings.LLM_FALLBACK_CHAIN",
        "ollama,openrouter,openai",
    )

    assert AIClient()._fallback_chain() == [ModelProvider.OLLAMA.value]


def test_development_tunnel_has_cold_start_timeout_headroom(monkeypatch):
    monkeypatch.setattr(
        "app.services.integration.ai_client.settings.LLM_RUNTIME_MODE",
        "development_tunnel",
    )
    monkeypatch.setattr(
        "app.services.integration.ai_client.settings.LLM_TIMEOUT_SECONDS",
        30.0,
    )

    assert AIClient()._provider_timeout_seconds() == 150.0


def test_ollama_request_headers_accepts_cloudflare_access_headers(monkeypatch):
    monkeypatch.setattr(
        "app.services.integration.ai_client.settings.OLLAMA_REQUEST_HEADERS_JSON",
        '{"CF-Access-Client-Id":"client-id","CF-Access-Client-Secret":"secret"}',
    )

    assert AIClient()._ollama_request_headers() == {
        "CF-Access-Client-Id": "client-id",
        "CF-Access-Client-Secret": "secret",
    }


def test_ollama_request_headers_rejects_invalid_json(monkeypatch):
    monkeypatch.setattr(
        "app.services.integration.ai_client.settings.OLLAMA_REQUEST_HEADERS_JSON",
        "not-json",
    )

    with pytest.raises(ValueError, match="valid JSON"):
        AIClient()._ollama_request_headers()


@pytest.mark.asyncio
async def test_ollama_success(monkeypatch):
    monkeypatch.setattr("app.services.integration.ai_client.settings.MODEL_PROVIDER", "ollama")
    monkeypatch.setattr("app.services.integration.ai_client.settings.LLM_FALLBACK_CHAIN", "ollama")

    health_response = MagicMock(status_code=200)
    chat_response = MagicMock()
    chat_response.raise_for_status = MagicMock()
    chat_response.json.return_value = {
        "model": "llama3:8b-instruct",
        "message": {"role": "assistant", "content": "Hello from Ollama"},
    }

    clients = [
        _make_async_client_mock(get_response=health_response),
        _make_async_client_mock(post_response=chat_response),
    ]

    with patch(
        "app.services.integration.ai_client.httpx.AsyncClient",
        side_effect=clients,
    ):
        client = AIClient(provider=ModelProvider.OLLAMA)
        result = await client.chat_completion(
            messages=[{"role": "user", "content": "Hi"}]
        )

    assert result["provider"] == "ollama"
    assert result["content"] == "Hello from Ollama"
    chat_payload = clients[1].post.await_args.kwargs["json"]
    assert chat_payload["keep_alive"] == "30m"


@pytest.mark.asyncio
async def test_local_openai_compatible_success_includes_routing_telemetry(monkeypatch):
    monkeypatch.setattr("app.services.integration.ai_client.settings.LLM_PRIMARY_PROVIDER", "local")
    monkeypatch.setattr("app.services.integration.ai_client.settings.LLM_FALLBACK_CHAIN", "local")

    health_response = MagicMock(status_code=200)
    chat_response = MagicMock()
    chat_response.raise_for_status = MagicMock()
    chat_response.json.return_value = {
        "model": "chessrun-local",
        "choices": [{"message": {"content": "Focus on your opening choices."}}],
        "usage": {"total_tokens": 42},
    }

    with patch(
        "app.services.integration.ai_client.httpx.AsyncClient",
        side_effect=[
            _make_async_client_mock(get_response=health_response),
            _make_async_client_mock(post_response=chat_response),
        ],
    ):
        result = await AIClient().chat_completion(
            messages=[{"role": "user", "content": "What should I improve?"}]
        )

    assert result["provider"] == "local"
    assert result["model"] == "chessrun-local"
    assert result["fallback_used"] is False
    assert isinstance(result["latency_ms"], int)


@pytest.mark.asyncio
async def test_mock_provider_is_forbidden_in_production(monkeypatch):
    monkeypatch.setattr("app.services.integration.ai_client.settings.ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="mock: disabled in production"):
        await AIClient(provider=ModelProvider.MOCK).chat_completion(
            messages=[{"role": "user", "content": "Hello"}]
        )


@pytest.mark.asyncio
async def test_fallback_ollama_fails_openrouter_succeeds(monkeypatch):
    monkeypatch.setattr("app.services.integration.ai_client.settings.MODEL_PROVIDER", "")
    monkeypatch.setattr(
        "app.services.integration.ai_client.settings.LLM_FALLBACK_CHAIN",
        "ollama,openrouter",
    )
    monkeypatch.setattr("app.services.integration.ai_client.settings.OPENROUTER_API_KEY", "test-key")

    health_response = MagicMock(status_code=200)
    ollama_error_response = MagicMock()
    ollama_error_response.raise_for_status.side_effect = httpx.HTTPError("ollama down")

    openrouter_response = MagicMock()
    openrouter_response.raise_for_status = MagicMock()
    openrouter_response.json.return_value = {
        "model": "google/gemma-2-9b-it:free",
        "choices": [{"message": {"content": "Hello from OpenRouter"}}],
        "usage": {"total_tokens": 12},
    }

    clients = [
        _make_async_client_mock(get_response=health_response),
        _make_async_client_mock(post_response=ollama_error_response),
    ]

    mock_openrouter_client = AsyncMock()
    mock_openrouter_client.post = AsyncMock(return_value=openrouter_response)

    with patch(
        "app.services.integration.ai_client.httpx.AsyncClient",
        side_effect=clients,
    ), patch.object(
        AIClient,
        "_get_openrouter_client",
        return_value=mock_openrouter_client,
    ):
        client = AIClient(provider=ModelProvider.OPENROUTER)
        result = await client.chat_completion_with_fallback(
            messages=[{"role": "user", "content": "Hi"}]
        )

    assert result["provider"] == "openrouter"
    assert result["content"] == "Hello from OpenRouter"
    mock_openrouter_client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_all_providers_fail_raises(monkeypatch):
    monkeypatch.setattr("app.services.integration.ai_client.settings.MODEL_PROVIDER", "")
    monkeypatch.setattr(
        "app.services.integration.ai_client.settings.LLM_FALLBACK_CHAIN",
        "ollama,openrouter",
    )
    monkeypatch.setattr("app.services.integration.ai_client.settings.OPENROUTER_API_KEY", "test-key")

    with patch.object(AIClient, "_ollama_health_check", AsyncMock(return_value=False)), patch.object(
        AIClient,
        "_openrouter_chat",
        AsyncMock(side_effect=httpx.HTTPError("openrouter down")),
    ):
        client = AIClient(provider=ModelProvider.OPENROUTER)

        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            await client.chat_completion_with_fallback(
                messages=[{"role": "user", "content": "Hi"}]
            )


@pytest.mark.asyncio
async def test_missing_keys_skip_provider(monkeypatch):
    monkeypatch.setattr("app.services.integration.ai_client.settings.MODEL_PROVIDER", "")
    monkeypatch.setattr(
        "app.services.integration.ai_client.settings.LLM_FALLBACK_CHAIN",
        "openrouter,openai",
    )
    monkeypatch.setattr("app.services.integration.ai_client.settings.OPENROUTER_API_KEY", "")
    monkeypatch.setattr("app.services.integration.ai_client.settings.OPENAI_API_KEY", "")

    client = AIClient(provider=ModelProvider.OPENROUTER)

    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        await client.chat_completion_with_fallback(
            messages=[{"role": "user", "content": "Hi"}]
        )
