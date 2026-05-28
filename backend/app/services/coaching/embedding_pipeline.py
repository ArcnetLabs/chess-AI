"""Pattern embedding pipeline — populate semantic_memory after detection (P3-CM-02).

MVP scope: player patterns only. Game-summary chunks deferred to a later unit.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.pattern import PlayerPattern
from app.models.semantic_memory import SemanticMemory
from app.services.coaching.embedding_service import (
    embed_texts_sync,
    is_embedding_configured,
)

CONTENT_TYPE_PATTERN = "pattern"


def build_pattern_embedding_text(pattern: PlayerPattern) -> str:
    """Build a concise text summary for pattern embedding."""
    strength_label = "strength" if pattern.is_strength else "weakness"
    parts = [
        f"{pattern.pattern_type}/{pattern.pattern_subtype}",
        f"severity={pattern.severity}",
        f"occurrences={pattern.occurrence_count}",
        f"type={strength_label}",
        pattern.pattern_description.strip(),
    ]
    return " | ".join(part for part in parts if part)


def _serialize_embedding(embedding: list[float]) -> Any:
    """Store vectors as JSON text on SQLite/pytest; native vector on PostgreSQL."""
    if os.getenv("TESTING") == "1" or os.getenv("DATABASE_URL", "").startswith(
        "sqlite"
    ):
        return json.dumps(embedding)
    return embedding


def upsert_semantic_memory(
    db: Session,
    user_id: int,
    content_type: str,
    content_id: int,
    content_text: str,
    embedding: list[float],
    metadata: Optional[dict[str, Any]] = None,
) -> SemanticMemory:
    """Create or update a semantic_memory row keyed by user + type + content_id."""
    row = (
        db.query(SemanticMemory)
        .filter(
            SemanticMemory.user_id == user_id,
            SemanticMemory.content_type == content_type,
            SemanticMemory.content_id == content_id,
        )
        .first()
    )

    stored_embedding = _serialize_embedding(embedding)
    now = datetime.now(timezone.utc)

    if row is None:
        row = SemanticMemory(
            user_id=user_id,
            content_type=content_type,
            content_id=content_id,
            content_text=content_text,
            embedding=stored_embedding,
            memory_metadata=metadata,
        )
        db.add(row)
    else:
        row.content_text = content_text
        row.embedding = stored_embedding
        row.memory_metadata = metadata
        row.updated_at = now

    db.commit()
    db.refresh(row)
    return row


def _pattern_needs_sync(
    pattern: PlayerPattern,
    memory: Optional[SemanticMemory],
) -> bool:
    if memory is None or memory.embedding is None:
        return True
    pattern_updated = pattern.updated_at
    memory_updated = memory.updated_at
    if pattern_updated is None or memory_updated is None:
        return True
    if pattern_updated.tzinfo is None:
        pattern_updated = pattern_updated.replace(tzinfo=timezone.utc)
    if memory_updated.tzinfo is None:
        memory_updated = memory_updated.replace(tzinfo=timezone.utc)
    return pattern_updated > memory_updated


def sync_user_pattern_embeddings(db: Session, user_id: int) -> dict[str, Any]:
    """
    Embed and upsert semantic_memory rows for stale or missing player patterns.

    Returns stats: ``{status, embedded_count, skipped_count, reason?}``.
    """
    if not is_embedding_configured():
        if not settings.EMBEDDING_ENABLED:
            reason = "embedding disabled"
        else:
            reason = "embedding not configured (missing API key)"
        patterns = (
            db.query(PlayerPattern).filter(PlayerPattern.user_id == user_id).all()
        )
        return {
            "status": "skipped",
            "embedded_count": 0,
            "skipped_count": len(patterns),
            "reason": reason,
        }

    patterns = db.query(PlayerPattern).filter(PlayerPattern.user_id == user_id).all()
    if not patterns:
        return {
            "status": "success",
            "embedded_count": 0,
            "skipped_count": 0,
        }

    memory_by_content_id: dict[int, SemanticMemory] = {}
    for memory in (
        db.query(SemanticMemory)
        .filter(
            SemanticMemory.user_id == user_id,
            SemanticMemory.content_type == CONTENT_TYPE_PATTERN,
        )
        .all()
    ):
        if memory.content_id is not None:
            memory_by_content_id[int(memory.content_id)] = memory

    to_sync: list[PlayerPattern] = []
    skipped_count = 0
    for pattern in patterns:
        memory = memory_by_content_id.get(pattern.id)
        if _pattern_needs_sync(pattern, memory):
            to_sync.append(pattern)
        else:
            skipped_count += 1

    if not to_sync:
        return {
            "status": "success",
            "embedded_count": 0,
            "skipped_count": skipped_count,
        }

    texts = [build_pattern_embedding_text(p) for p in to_sync]
    try:
        embeddings = embed_texts_sync(texts)
    except Exception as exc:
        logger.error(f"Pattern embedding failed for user_id={user_id}: {exc}")
        return {
            "status": "failed",
            "embedded_count": 0,
            "skipped_count": skipped_count + len(to_sync),
            "reason": str(exc),
        }

    embedded_count = 0
    for pattern, text, vector in zip(to_sync, texts, embeddings):
        upsert_semantic_memory(
            db,
            user_id=user_id,
            content_type=CONTENT_TYPE_PATTERN,
            content_id=pattern.id,
            content_text=text,
            embedding=vector,
            metadata={
                "pattern_type": pattern.pattern_type,
                "pattern_subtype": pattern.pattern_subtype,
                "severity": pattern.severity,
                "occurrence_count": pattern.occurrence_count,
            },
        )
        embedded_count += 1

    logger.info(
        f"Pattern embeddings synced user_id={user_id}: "
        f"embedded={embedded_count} skipped={skipped_count}"
    )
    return {
        "status": "success",
        "embedded_count": embedded_count,
        "skipped_count": skipped_count,
    }
