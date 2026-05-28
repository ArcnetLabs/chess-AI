"""OpenAI-compatible text embedding client for semantic memory (P3-CM-02)."""
from __future__ import annotations

import asyncio
import os
from typing import Optional

import httpx
from loguru import logger

from app.core.config import settings

EMBEDDING_DIM = 1536

_http_client: Optional[httpx.AsyncClient] = None


def is_embedding_configured() -> bool:
    """Return True when embeddings are enabled and an API key is present."""
    if not settings.EMBEDDING_ENABLED:
        return False
    return bool(settings.OPENAI_API_KEY)


def _use_mock_embeddings() -> bool:
    """Use zero-vector mock when no API key (tests/local dev — no network)."""
    return not bool(settings.OPENAI_API_KEY)


def _mock_embeddings(texts: list[str]) -> list[list[float]]:
    return [[0.0] * EMBEDDING_DIM for _ in texts]


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            base_url=settings.OPENAI_API_BASE.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            timeout=60.0,
        )
    return _http_client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts via OpenAI-compatible ``/embeddings`` API.

    Returns zero vectors when no API key is configured (mock mode for tests).
    """
    if not texts:
        return []

    if _use_mock_embeddings():
        logger.debug(f"Mock embedding {len(texts)} text(s) (no OPENAI_API_KEY)")
        return _mock_embeddings(texts)

    batch_size = max(1, settings.EMBEDDING_BATCH_SIZE)
    client = _get_http_client()
    all_embeddings: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        payload = {
            "model": settings.EMBEDDING_MODEL,
            "input": batch,
        }
        try:
            response = await client.post("/embeddings", json=payload)
            response.raise_for_status()
            data = response.json()
            ordered = sorted(data["data"], key=lambda row: row["index"])
            all_embeddings.extend(row["embedding"] for row in ordered)
        except httpx.HTTPError as exc:
            logger.error(f"Embedding API error: {exc}")
            raise

    return all_embeddings


def embed_texts_sync(texts: list[str]) -> list[list[float]]:
    """Sync wrapper for Celery tasks and other non-async callers."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(embed_texts(texts))

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, embed_texts(texts)).result()


async def close_embedding_client() -> None:
    """Close the shared httpx client (app shutdown hooks)."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
