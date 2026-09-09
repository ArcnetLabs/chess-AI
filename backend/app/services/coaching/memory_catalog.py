"""Catalog access to a user's semantic memories (redesign P4).

Powers the "What your coach knows" surface: a read-only listing of the
coaching exchanges and analysis patterns that back the coach's grounding.
Deliberately excludes embeddings — this is a catalog, not a retrieval path.
"""
from __future__ import annotations

from sqlalchemy.orm import Session, defer

from ...models.semantic_memory import SemanticMemory


def list_memories(
    db: Session,
    user_id: int,
    content_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[SemanticMemory]:
    """Return the user's semantic memories, newest first.

    ``content_type`` optionally filters to one slice ('pattern' or
    'coaching'). Embedding columns are deferred — they are 768-dim vectors
    and must never reach the API layer.
    """
    query = db.query(SemanticMemory).filter(SemanticMemory.user_id == user_id)
    if content_type:
        query = query.filter(SemanticMemory.content_type == content_type)
    return (
        query.options(defer(SemanticMemory.embedding))
        .order_by(SemanticMemory.created_at.desc(), SemanticMemory.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_memories(
    db: Session,
    user_id: int,
    content_type: str | None = None,
) -> int:
    """Count the user's memories, optionally within one slice."""
    query = db.query(SemanticMemory).filter(SemanticMemory.user_id == user_id)
    if content_type:
        query = query.filter(SemanticMemory.content_type == content_type)
    return query.count()
