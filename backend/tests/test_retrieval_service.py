"""Tests for semantic memory retrieval service (P3-CM-03)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.config import settings
from app.models.user import User
from app.services.coaching.embedding_pipeline import (
    CONTENT_TYPE_PATTERN,
    upsert_semantic_memory,
)
from app.services.coaching.embedding_service import EMBEDDING_DIM
from app.services.coaching.retrieval_service import (
    format_retrieved_memories_for_context,
    retrieve_semantic_memories,
    retrieve_semantic_memories_async,
)


def _create_user(db) -> User:
    user = User(
        email="retrieval@example.com",
        supabase_user_id="retrieval-user-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _unit_vector(index: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    vector[index] = 1.0
    return vector


def _seed_memories(db, user_id: int) -> None:
    upsert_semantic_memory(
        db,
        user_id=user_id,
        content_type=CONTENT_TYPE_PATTERN,
        content_id=1,
        content_text="Pattern aligned with dimension 0",
        embedding=_unit_vector(0),
        metadata={"axis": "x"},
    )
    upsert_semantic_memory(
        db,
        user_id=user_id,
        content_type=CONTENT_TYPE_PATTERN,
        content_id=2,
        content_text="Pattern aligned with dimension 1",
        embedding=_unit_vector(1),
        metadata={"axis": "y"},
    )
    upsert_semantic_memory(
        db,
        user_id=user_id,
        content_type="coaching",
        content_id=3,
        content_text="Prior coaching note on endgames",
        embedding=_unit_vector(0),
        metadata={"topic": "endgame"},
    )


@patch("app.services.coaching.retrieval_service.embed_texts_sync")
def test_retrieve_returns_highest_similarity_first(mock_embed, db, monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    mock_embed.return_value = [_unit_vector(0)]

    user = _create_user(db)
    _seed_memories(db, user.id)

    results = retrieve_semantic_memories(
        db,
        user.id,
        "why do I miss forks?",
        limit=3,
    )

    assert len(results) == 3
    assert results[0].similarity_score >= results[1].similarity_score
    assert results[0].content_id == 1
    assert results[0].content_text == "Pattern aligned with dimension 0"
    assert results[0].similarity_score == pytest.approx(1.0)
    mock_embed.assert_called_once_with(["why do I miss forks?"])


@patch("app.services.coaching.retrieval_service.embed_texts_sync")
def test_retrieve_filters_by_content_types(mock_embed, db, monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    mock_embed.return_value = [_unit_vector(0)]

    user = _create_user(db)
    _seed_memories(db, user.id)

    results = retrieve_semantic_memories(
        db,
        user.id,
        "endgame conversion",
        content_types=["coaching"],
        limit=5,
    )

    assert len(results) == 1
    assert results[0].content_type == "coaching"
    assert results[0].content_id == 3


@patch("app.services.coaching.retrieval_service.embed_texts_sync")
def test_retrieve_returns_empty_when_embedding_disabled(mock_embed, db, monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", False)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    user = _create_user(db)
    _seed_memories(db, user.id)

    results = retrieve_semantic_memories(db, user.id, "any query")

    assert results == []
    mock_embed.assert_not_called()


@patch("app.services.coaching.retrieval_service.embed_texts")
@pytest.mark.asyncio
async def test_retrieve_async_uses_embed_texts(mock_embed, db, monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    mock_embed.return_value = [_unit_vector(1)]

    user = _create_user(db)
    _seed_memories(db, user.id)

    results = await retrieve_semantic_memories_async(
        db,
        user.id,
        "orthogonal pattern",
        limit=2,
    )

    assert len(results) == 2
    assert results[0].content_id == 2
    assert results[0].similarity_score == pytest.approx(1.0)
    mock_embed.assert_called_once_with(["orthogonal pattern"])


def test_format_retrieved_memories_for_context():
    from app.services.coaching.retrieval_service import RetrievedMemory

    memories = [
        RetrievedMemory(
            id=1,
            content_type="pattern",
            content_id=10,
            content_text="Missed rook endgame conversions.",
            similarity_score=0.91,
            metadata={"severity": "critical"},
        )
    ]

    formatted = format_retrieved_memories_for_context(memories)

    assert "## Relevant Semantic Memories" in formatted
    assert "pattern, 91% match" in formatted
    assert "Missed rook endgame conversions." in formatted
    assert "severity=critical" in formatted


def test_format_retrieved_memories_empty():
    assert format_retrieved_memories_for_context([]) == ""
