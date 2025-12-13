"""
AI Model Provider Abstraction Layer.

Supports multiple AI providers (OpenAI, OpenRouter) with unified interface.
Provider selection via MODEL_PROVIDER environment variable.
"""
import os
from typing import Optional, Dict, Any, List
from enum import Enum
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
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    MOCK = "mock"  # For testing without API calls


class AIClient:
    """
    Unified AI client supporting multiple providers.
    
    Usage:
        client = AIClient()
        response = await client.chat_completion(
            messages=[{"role": "user", "content": "Hello!"}],
            model="gpt-4"
        )
    """
    
    def __init__(
        self,
        provider: Optional[ModelProvider] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize AI client with specified provider.
        
        Args:
            provider: AI provider to use (defaults to settings)
            api_key: API key for the provider (defaults to env var)
        """
        self.provider = provider or self._get_default_provider()
        self.api_key = api_key or self._get_api_key()
        
        if self.provider == ModelProvider.OPENAI:
            self._init_openai()
        elif self.provider == ModelProvider.OPENROUTER:
            self._init_openrouter()
        elif self.provider == ModelProvider.MOCK:
            self._init_mock()
        
        logger.info(f"AI Client initialized with provider: {self.provider}")
    
    def _get_default_provider(self) -> ModelProvider:
        """Determine default provider based on environment."""
        provider_str = os.getenv("MODEL_PROVIDER", "").lower()
        
        # Development mode defaults to OpenRouter (free tier)
        if settings.LOG_LEVEL == "DEBUG" and not provider_str:
            return ModelProvider.OPENROUTER
        
        # Map string to enum
        provider_map = {
            "openai": ModelProvider.OPENAI,
            "openrouter": ModelProvider.OPENROUTER,
            "mock": ModelProvider.MOCK
        }
        
        return provider_map.get(provider_str, ModelProvider.OPENROUTER)
    
    def _get_api_key(self) -> str:
        """Get API key for current provider."""
        if self.provider == ModelProvider.OPENAI:
            key = os.getenv("OPENAI_API_KEY", "")
            if not key:
                logger.warning("OPENAI_API_KEY not set")
            return key
        
        elif self.provider == ModelProvider.OPENROUTER:
            key = os.getenv("OPENROUTER_API_KEY", "")
            if not key:
                logger.warning("OPENROUTER_API_KEY not set")
            return key
        
        return "mock-api-key"
    
    def _init_openai(self):
        """Initialize OpenAI client."""
        if not OPENAI_AVAILABLE:
            raise ImportError("openai library not installed. Run: pip install openai")
        
        openai.api_key = self.api_key
        self.base_url = "https://api.openai.com/v1"
    
    def _init_openrouter(self):
        """Initialize OpenRouter client."""
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx library required for OpenRouter. Run: pip install httpx")
        
        self.base_url = "https://openrouter.ai/api/v1"
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://chess-insight-ai.com",  # Optional
                "X-Title": "Chess Insight AI"  # Optional
            },
            timeout=30.0
        )
    
    def _init_mock(self):
        """Initialize mock client for testing."""
        self.base_url = "mock://api"
        logger.info("Mock AI client initialized (for testing)")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate chat completion across providers.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model identifier (provider-specific)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
        
        Returns:
            Standardized response dict with 'content' and 'usage'
        """
        if self.provider == ModelProvider.OPENAI:
            return await self._openai_chat(messages, model, temperature, max_tokens, **kwargs)
        
        elif self.provider == ModelProvider.OPENROUTER:
            return await self._openrouter_chat(messages, model, temperature, max_tokens, **kwargs)
        
        elif self.provider == ModelProvider.MOCK:
            return self._mock_chat(messages, model, temperature, max_tokens, **kwargs)
        
        raise ValueError(f"Unsupported provider: {self.provider}")
    
    async def _openai_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> Dict[str, Any]:
        """OpenAI chat completion."""
        model = model or "gpt-4o-mini"  # Default to cost-effective model
        
        try:
            response = await openai.ChatCompletion.acreate(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            return {
                "content": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "model": response.model,
                "provider": "openai"
            }
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    async def _openrouter_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> Dict[str, Any]:
        """
        OpenRouter chat completion.
        
        Free models available:
        - google/gemma-2-9b-it:free
        - meta-llama/llama-3.1-8b-instruct:free
        - mistralai/mistral-7b-instruct:free
        """
        # Default to free model for development
        model = model or "google/gemma-2-9b-it:free"
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        payload.update(kwargs)
        
        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            
            return {
                "content": data["choices"][0]["message"]["content"],
                "usage": data.get("usage", {}),
                "model": data.get("model", model),
                "provider": "openrouter"
            }
        except httpx.HTTPError as e:
            logger.error(f"OpenRouter API error: {e}")
            raise
    
    def _mock_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> Dict[str, Any]:
        """Mock chat completion for testing."""
        last_message = messages[-1]["content"] if messages else ""
        
        return {
            "content": f"Mock response to: {last_message[:50]}...",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            },
            "model": model or "mock-model",
            "provider": "mock"
        }
    
    async def close(self):
        """Close any open connections."""
        if hasattr(self, "client") and self.client:
            await self.client.aclose()


# Singleton instance
_ai_client: Optional[AIClient] = None


def get_ai_client() -> AIClient:
    """Get or create AI client singleton."""
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client


async def close_ai_client():
    """Close AI client connections."""
    global _ai_client
    if _ai_client:
        await _ai_client.close()
        _ai_client = None
