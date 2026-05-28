"""Semantic memory retrieval for coaching context (P3-CM-03).

PostgreSQL uses pgvector cosine distance; SQLite/pytest parses JSON embeddings
and ranks in Python so tests run without the pgvector extension.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.semantic_memory import SemanticMemory
from app.services.coaching.embedding_service import (
    EMBEDDING_DIM,
    embed_texts,
    embed_texts_sync,
    is_embedding_configured,
)


@dataclass
class RetrievedMemory:
    id: int
    content_type: str
    content_id: int | None
    content_text: str
    similarity_score: float
    metadata: dict | None


def _use_json_embeddings() -> bool:
    """True when embeddings are stored as JSON text (SQLite / pytest)."""
    return os.getenv("TESTING") == "1" or os.getenv("DATABASE_URL", "").startswith(
        "sqlite"
    )


def _parse_embedding(raw: Any) -> list[float] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, list) or not parsed:
            return None
        return [float(x) for x in parsed]
    if isinstance(raw, (list, tuple)):
        if not raw:
            return None
        return [float(x) for x in raw]
    return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _base_query(db: Session, user_id: int, content_types: list[str] | None):
    query = db.query(SemanticMemory).filter(SemanticMemory.user_id == user_id)
    if content_types:
        query = query.filter(SemanticMemory.content_type.in_(content_types))
    return query.filter(SemanticMemory.embedding.isnot(None))


def _retrieve_sqlite(
    db: Session,
    user_id: int,
    query_vector: list[float],
    *,
    content_types: list[str] | None,
    limit: int,
    min_similarity: float,
) -> list[RetrievedMemory]:
    rows = _base_query(db, user_id, content_types).all()
    scored: list[RetrievedMemory] = []

    for row in rows:
        stored = _parse_embedding(row.embedding)
        if stored is None:
            continue
        similarity = _cosine_similarity(query_vector, stored)
        if similarity < min_similarity:
            continue
        scored.append(
            RetrievedMemory(
                id=row.id,
                content_type=row.content_type,
                content_id=int(row.content_id) if row.content_id is not None else None,
                content_text=row.content_text,
                similarity_score=similarity,
                metadata=row.memory_metadata,
            )
        )

    scored.sort(key=lambda m: m.similarity_score, reverse=True)
    return scored[:limit]


def _retrieve_postgres(
    db: Session,
    user_id: int,
    query_vector: list[float],
    *,
    content_types: list[str] | None,
    limit: int,
    min_similarity: float,
) -> list[RetrievedMemory]:
    if len(query_vector) != EMBEDDING_DIM:
        logger.warning(
            f"Query embedding dim {len(query_vector)} != expected {EMBEDDING_DIM}"
        )

    vector_literal = _vector_literal(query_vector)

    sql_parts = [
        """
        SELECT
            id,
            content_type,
            content_id,
            content_text,
            metadata,
            1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity_score
        FROM semantic_memory
        WHERE user_id = :user_id
          AND embedding IS NOT NULL
          AND (1 - (embedding <=> CAST(:query_vec AS vector))) >= :min_similarity
        """
    ]
    params: dict[str, Any] = {
        "user_id": user_id,
        "query_vec": vector_literal,
        "min_similarity": min_similarity,
        "limit": limit,
    }

    if content_types:
        sql_parts.append("AND content_type = ANY(:content_types)")
        params["content_types"] = content_types

    sql_parts.append(
        """
        ORDER BY embedding <=> CAST(:query_vec AS vector)
        LIMIT :limit
        """
    )

    result = db.execute(text(" ".join(sql_parts)), params)
    memories: list[RetrievedMemory] = []
    for row in result:
        similarity = float(row.similarity_score)
        if similarity < min_similarity:
            continue
        memories.append(
            RetrievedMemory(
                id=int(row.id),
                content_type=str(row.content_type),
                content_id=int(row.content_id) if row.content_id is not None else None,
                content_text=str(row.content_text),
                similarity_score=similarity,
                metadata=row.metadata,
            )
        )
    return memories


def retrieve_semantic_memories(
    db: Session,
    user_id: int,
    query_text: str,
    *,
    content_types: list[str] | None = None,
    limit: int = 5,
    min_similarity: float = 0.0,
) -> list[RetrievedMemory]:
    """
    Retrieve top semantic memories for a user query (sync — Celery / sync callers).

    Returns an empty list when embeddings are not configured.
    """
    if not is_embedding_configured():
        logger.info(
            "Semantic memory retrieval skipped for user_id={}: embedding not configured",
            user_id,
        )
        return []

    try:
        embeddings = embed_texts_sync([query_text])
    except Exception as exc:
        logger.error(f"Query embedding failed for user_id={user_id}: {exc}")
        return []

    if not embeddings:
        return []

    query_vector = embeddings[0]

    if _use_json_embeddings():
        return _retrieve_sqlite(
            db,
            user_id,
            query_vector,
            content_types=content_types,
            limit=limit,
            min_similarity=min_similarity,
        )

    return _retrieve_postgres(
        db,
        user_id,
        query_vector,
        content_types=content_types,
        limit=limit,
        min_similarity=min_similarity,
    )


async def retrieve_semantic_memories_async(
    db: Session,
    user_id: int,
    query_text: str,
    *,
    content_types: list[str] | None = None,
    limit: int = 5,
    min_similarity: float = 0.0,
) -> list[RetrievedMemory]:
    """Async variant — embeds the query via ``embed_texts``."""
    if not is_embedding_configured():
        logger.info(
            "Semantic memory retrieval skipped for user_id={}: embedding not configured",
            user_id,
        )
        return []

    try:
        embeddings = await embed_texts([query_text])
    except Exception as exc:
        logger.error(f"Query embedding failed for user_id={user_id}: {exc}")
        return []

    if not embeddings:
        return []

    query_vector = embeddings[0]

    if _use_json_embeddings():
        return _retrieve_sqlite(
            db,
            user_id,
            query_vector,
            content_types=content_types,
            limit=limit,
            min_similarity=min_similarity,
        )

    return _retrieve_postgres(
        db,
        user_id,
        query_vector,
        content_types=content_types,
        limit=limit,
        min_similarity=min_similarity,
    )


def format_retrieved_memories_for_context(memories: list[RetrievedMemory]) -> str:
    """Compact markdown block for coach prompt assembly (P3-CM-04)."""
    if not memories:
        return ""

    lines = ["## Relevant Semantic Memories", ""]
    for index, memory in enumerate(memories, start=1):
        score_pct = int(round(memory.similarity_score * 100))
        lines.append(
            f"### Memory {index} ({memory.content_type}, {score_pct}% match)"
        )
        lines.append(memory.content_text)
        if memory.metadata:
            meta = ", ".join(f"{key}={value}" for key, value in memory.metadata.items())
            lines.append(f"*Metadata: {meta}*")
        lines.append("")

    return "\n".join(lines).strip()
