"""OpenAI-compatible text embedding client for semantic memory (P3-CM-02).

Client lifetime: the HTTP client is built per call and closed with the call.
Celery reaches this module through :func:`embed_texts_sync`, which runs every
call on its own ``asyncio.run`` loop, so a cached client outlives the loop that
owns its pooled keep-alive connections — the next invocation then dies with
``RuntimeError: Event loop is closed`` instead of embedding anything.
"""
from __future__ import annotations

import asyncio
import os

import httpx
from loguru import logger

from app.core.config import settings

EMBEDDING_DIM = 768


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


def _build_http_client() -> httpx.AsyncClient:
    """Build a client owned by the loop that runs the current call."""
    return httpx.AsyncClient(
        base_url=settings.OPENAI_API_BASE.rstrip("/"),
        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
        timeout=60.0,
    )


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
    all_embeddings: list[list[float]] = []

    async with _build_http_client() as client:
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            payload = {
                "model": settings.EMBEDDING_MODEL,
                "input": batch,
            }
            if settings.EMBEDDING_DIMENSIONS is not None:
                payload["dimensions"] = settings.EMBEDDING_DIMENSIONS
            try:
                response = await client.post("/embeddings", json=payload)
                response.raise_for_status()
                data = response.json()
                # OpenAI returns an "index" per item; some OpenAI-compatible
                # providers (e.g. Gemini) omit it — fall back to payload order.
                ordered = sorted(
                    enumerate(data["data"]),
                    key=lambda pair: pair[1].get("index", pair[0]),
                )
                all_embeddings.extend(row["embedding"] for _, row in ordered)
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
