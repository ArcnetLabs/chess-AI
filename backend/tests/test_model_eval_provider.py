"""Tests for the model-probe provider wiring.

Written after the harness failed in production on its first real run:

    probe endgame_position provider failed: cannot import name
    'chat_completion_with_fallback' from 'app.services.integration.ai_client'

The provider path had never executed — there are no LLM credentials in a local
checkout or in CI, so every test of the harness used a fake provider and the real
wiring was never touched. These tests exercise the wiring itself, without calling a
model: they check that the symbol the provider resolves actually exists and is
callable, which is exactly what was wrong.
"""

import inspect
from unittest.mock import patch

import pytest

from app.services.evaluation.coach_probes import _provider_from_settings
from app.services.integration import ai_client


class TestProviderWiring:
    def test_the_client_api_the_provider_calls_exists(self):
        """The contract, checked without a model call: class + fallback method."""
        assert hasattr(ai_client, "get_ai_client"), (
            "the provider builds a client through get_ai_client()"
        )
        client_cls = ai_client.AIClient
        assert hasattr(client_cls, "chat_completion_with_fallback"), (
            "AIClient.chat_completion_with_fallback is what the provider awaits"
        )
        assert inspect.iscoroutinefunction(client_cls.chat_completion_with_fallback)

    def test_the_removed_module_level_function_is_not_assumed(self):
        """Guard against reintroducing the exact import that broke production."""
        assert not hasattr(ai_client, "chat_completion_with_fallback"), (
            "if this ever becomes a module-level function, update the provider — but "
            "do not assume it exists without checking, which is what failed in prod"
        )

    def test_no_credentials_means_no_provider(self):
        with patch.dict("os.environ", {}, clear=True):
            assert _provider_from_settings() is None

    def test_credentials_produce_a_callable_provider(self):
        with patch.dict("os.environ", {"LLM_LOCAL_API_KEY": "test-key"}, clear=True):
            provider = _provider_from_settings()
        assert callable(provider)

    def test_the_provider_resolves_a_real_client_when_called(self):
        """Calls the provider with the model stubbed at the client boundary.

        This is the layer the production failure lived in: the provider could be
        constructed fine and only broke when it tried to resolve what to call.
        """
        with patch.dict("os.environ", {"LLM_LOCAL_API_KEY": "test-key"}, clear=True):
            provider = _provider_from_settings()

        class _Stub:
            async def chat_completion_with_fallback(self, messages, **kwargs):
                self.messages = messages
                return {"content": "stubbed reply"}

        stub = _Stub()
        with patch.object(ai_client, "get_ai_client", return_value=stub):
            reply = provider("system prompt", "user prompt")

        assert reply == "stubbed reply"
        assert stub.messages[0]["role"] == "system"
        assert stub.messages[-1]["content"] == "user prompt"

    def test_a_client_error_is_not_swallowed_into_a_fake_reply(self):
        """A failing provider must raise, so run_probes records the failure."""
        with patch.dict("os.environ", {"LLM_LOCAL_API_KEY": "test-key"}, clear=True):
            provider = _provider_from_settings()

        class _Broken:
            async def chat_completion_with_fallback(self, messages, **kwargs):
                raise RuntimeError("provider down")

        with patch.object(ai_client, "get_ai_client", return_value=_Broken()):
            with pytest.raises(RuntimeError):
                provider("system", "user")
