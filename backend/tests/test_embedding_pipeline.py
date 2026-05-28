"""Tests for pattern embedding pipeline (P3-CM-02)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.models.pattern import PlayerPattern
from app.models.semantic_memory import SemanticMemory
from app.models.user import User
from app.services.coaching.embedding_pipeline import (
    CONTENT_TYPE_PATTERN,
    build_pattern_embedding_text,
    sync_user_pattern_embeddings,
    upsert_semantic_memory,
)
from app.services.coaching.embedding_service import EMBEDDING_DIM
from app.tasks.embedding_tasks import (
    EMBEDDING_DEBOUNCE_KEY_PREFIX,
    schedule_pattern_embedding_for_user,
)


def _create_user(db) -> User:
    user = User(
        email="embed@example.com",
        supabase_user_id="embed-user-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_pattern(db, user: User, **overrides) -> PlayerPattern:
    pattern = PlayerPattern(
        user_id=user.id,
        pattern_type=overrides.get("pattern_type", "tactical"),
        pattern_subtype=overrides.get("pattern_subtype", "fork_miss"),
        severity=overrides.get("severity", "high"),
        confidence_score=overrides.get("confidence_score", 0.85),
        occurrence_count=overrides.get("occurrence_count", 12),
        affected_games_count=overrides.get("affected_games_count", 8),
        affected_games_ratio=overrides.get("affected_games_ratio", 0.4),
        pattern_description=overrides.get(
            "pattern_description",
            "Frequently misses knight fork opportunities in the middlegame.",
        ),
        is_strength=overrides.get("is_strength", False),
    )
    db.add(pattern)
    db.commit()
    db.refresh(pattern)
    return pattern


def test_build_pattern_embedding_text():
    pattern = PlayerPattern(
        user_id=1,
        pattern_type="opening",
        pattern_subtype="trap_falls",
        severity="medium",
        confidence_score=0.7,
        occurrence_count=5,
        affected_games_count=3,
        affected_games_ratio=0.2,
        pattern_description="Falls into early queen traps.",
        is_strength=False,
    )
    text = build_pattern_embedding_text(pattern)
    assert "opening/trap_falls" in text
    assert "severity=medium" in text
    assert "occurrences=5" in text
    assert "type=weakness" in text
    assert "Falls into early queen traps." in text


def test_upsert_creates_semantic_memory_row(db):
    user = _create_user(db)
    vector = [0.1] * EMBEDDING_DIM

    row = upsert_semantic_memory(
        db,
        user_id=user.id,
        content_type=CONTENT_TYPE_PATTERN,
        content_id=99,
        content_text="test pattern summary",
        embedding=vector,
        metadata={"pattern_type": "tactical"},
    )

    assert row.id is not None
    assert row.user_id == user.id
    assert row.content_type == CONTENT_TYPE_PATTERN
    assert row.content_id == 99
    assert row.content_text == "test pattern summary"
    assert row.memory_metadata["pattern_type"] == "tactical"
    stored = json.loads(row.embedding) if isinstance(row.embedding, str) else row.embedding
    assert len(stored) == EMBEDDING_DIM


def test_upsert_updates_existing_semantic_memory_row(db):
    user = _create_user(db)
    vector_a = [0.1] * EMBEDDING_DIM
    vector_b = [0.2] * EMBEDDING_DIM

    first = upsert_semantic_memory(
        db,
        user_id=user.id,
        content_type=CONTENT_TYPE_PATTERN,
        content_id=42,
        content_text="original text",
        embedding=vector_a,
        metadata={"version": 1},
    )
    first_id = first.id

    updated = upsert_semantic_memory(
        db,
        user_id=user.id,
        content_type=CONTENT_TYPE_PATTERN,
        content_id=42,
        content_text="updated text",
        embedding=vector_b,
        metadata={"version": 2},
    )

    assert updated.id == first_id
    assert updated.content_text == "updated text"
    assert updated.memory_metadata["version"] == 2


def test_sync_skips_when_embedding_disabled(db, monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", False)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    user = _create_user(db)
    _create_pattern(db, user)

    result = sync_user_pattern_embeddings(db, user.id)

    assert result["status"] == "skipped"
    assert result["embedded_count"] == 0
    assert result["skipped_count"] == 1
    assert result["reason"] == "embedding disabled"
    assert db.query(SemanticMemory).count() == 0


@patch("app.services.coaching.embedding_pipeline.embed_texts_sync")
def test_sync_embeds_stale_patterns(mock_embed, db, monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    mock_embed.return_value = [[0.5] * EMBEDDING_DIM]

    user = _create_user(db)
    pattern = _create_pattern(db, user)

    result = sync_user_pattern_embeddings(db, user.id)

    assert result["status"] == "success"
    assert result["embedded_count"] == 1
    assert result["skipped_count"] == 0
    mock_embed.assert_called_once()

    memory = (
        db.query(SemanticMemory)
        .filter(
            SemanticMemory.user_id == user.id,
            SemanticMemory.content_id == pattern.id,
        )
        .one()
    )
    assert memory.content_type == CONTENT_TYPE_PATTERN
    assert pattern.pattern_description in memory.content_text


@patch("app.services.coaching.embedding_pipeline.embed_texts_sync")
def test_sync_skips_up_to_date_patterns(mock_embed, db, monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    user = _create_user(db)
    pattern = _create_pattern(db, user)
    upsert_semantic_memory(
        db,
        user_id=user.id,
        content_type=CONTENT_TYPE_PATTERN,
        content_id=pattern.id,
        content_text="already embedded",
        embedding=[0.3] * EMBEDDING_DIM,
        metadata={},
    )

    result = sync_user_pattern_embeddings(db, user.id)

    assert result["status"] == "success"
    assert result["embedded_count"] == 0
    assert result["skipped_count"] == 1
    mock_embed.assert_not_called()


@patch("app.services.coaching.embedding_pipeline.embed_texts_sync")
def test_sync_reembeds_when_pattern_newer_than_memory(mock_embed, db, monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    mock_embed.return_value = [[0.7] * EMBEDDING_DIM]

    user = _create_user(db)
    pattern = _create_pattern(db, user)

    memory = upsert_semantic_memory(
        db,
        user_id=user.id,
        content_type=CONTENT_TYPE_PATTERN,
        content_id=pattern.id,
        content_text="stale text",
        embedding=[0.1] * EMBEDDING_DIM,
        metadata={},
    )
    memory.updated_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db.commit()

    pattern.pattern_description = "Updated description after new games."
    pattern.updated_at = datetime.now(timezone.utc)
    db.commit()

    result = sync_user_pattern_embeddings(db, user.id)

    assert result["embedded_count"] == 1
    mock_embed.assert_called_once()


@pytest.mark.asyncio
async def test_embed_texts_mock_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

    from app.services.coaching.embedding_service import embed_texts

    vectors = await embed_texts(["hello", "world"])
    assert len(vectors) == 2
    assert all(len(v) == EMBEDDING_DIM for v in vectors)
    assert all(x == 0.0 for x in vectors[0])


@patch("app.tasks.embedding_tasks.redis_client", None)
@patch("app.tasks.embedding_tasks.embed_user_patterns_task.apply_async")
def test_schedule_pattern_embedding_without_redis(mock_apply_async):
    scheduled = schedule_pattern_embedding_for_user(7, countdown=30)

    assert scheduled is True
    mock_apply_async.assert_called_once_with(args=[7], countdown=30)


@patch("app.tasks.embedding_tasks.redis_client")
@patch("app.tasks.embedding_tasks.embed_user_patterns_task.apply_async")
def test_schedule_pattern_embedding_debounce(mock_apply_async, mock_redis):
    mock_redis.set.return_value = False

    scheduled = schedule_pattern_embedding_for_user(9)

    assert scheduled is False
    mock_apply_async.assert_not_called()
    mock_redis.set.assert_called_once_with(
        f"{EMBEDDING_DEBOUNCE_KEY_PREFIX}:9",
        "1",
        nx=True,
        ex=120,
    )
