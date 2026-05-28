"""P3-CM-01 — semantic_memory model and schema scaffolding tests."""
import os

import pytest
from sqlalchemy import inspect

from app.models.semantic_memory import SemanticMemory
from app.models.user import User


def test_semantic_memory_model_imports():
    assert SemanticMemory.__tablename__ == "semantic_memory"


def test_semantic_memory_table_columns():
    mapper = inspect(SemanticMemory)
    column_names = {c.key for c in mapper.columns}
    expected = {
        "id",
        "user_id",
        "content_type",
        "content_id",
        "content_text",
        "embedding",
        "metadata",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(column_names)


def test_semantic_memory_create_on_sqlite(db):
    """Basic ORM round-trip on in-memory SQLite (Text embedding placeholder)."""
    assert os.getenv("TESTING") == "1"

    user = User(
        chesscom_username="vector_test_user",
        email="vector@test.example",
    )
    db.add(user)
    db.flush()

    row = SemanticMemory(
        user_id=user.id,
        content_type="pattern",
        content_id=42,
        content_text="Frequent knight fork misses in middlegame.",
        embedding=None,
        memory_metadata={"source": "pytest"},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    assert row.id is not None
    assert row.user_id == user.id
    assert row.content_type == "pattern"
    assert row.content_id == 42
    assert row.memory_metadata["source"] == "pytest"


def test_embedding_column_uses_text_under_pytest():
    """Model maps embedding to Text when TESTING=1 (SQLite create_all path)."""
    assert os.getenv("TESTING") == "1"
    col = SemanticMemory.__table__.c.embedding
    assert col.type.__class__.__name__ in ("Text", "TEXT")
