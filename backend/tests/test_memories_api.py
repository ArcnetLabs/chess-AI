"""Tests for the semantic-memory catalog API (redesign P4)."""

from datetime import datetime, timedelta

import pytest
from fastapi import status

from app.__main__ import app
from app.middleware.auth_middleware import get_current_user
from app.models.semantic_memory import SemanticMemory
from app.models.user import User


def _memory(user_id: int, content_type: str, text: str, age_days: int) -> SemanticMemory:
    created = datetime.utcnow() - timedelta(days=age_days)
    return SemanticMemory(
        user_id=user_id,
        content_type=content_type,
        content_text=text,
        created_at=created,
        updated_at=created,
    )


@pytest.fixture
def memory_user(db):
    user = User(
        email="memories-api@example.com",
        supabase_user_id="memories-api-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def other_user(db):
    user = User(
        email="memories-other@example.com",
        supabase_user_id="memories-other-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def authenticated_client(client, memory_user):
    async def override_get_current_user():
        return memory_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def _seed(db, memory_user):
    rows = [
        _memory(memory_user.id, "coaching", "Coaching exchange (2026-09-01). Player asked: openings?", age_days=1),
        _memory(memory_user.id, "coaching", "Coaching exchange (2026-08-20). Player asked: rook endgames?", age_days=2),
        _memory(memory_user.id, "pattern", "Player weakness in endgame: rook endgame technique.", age_days=3),
    ]
    db.add_all(rows)
    db.commit()


@pytest.mark.api
def test_list_memories_newest_first(authenticated_client, memory_user, db):
    _seed(db, memory_user)

    response = authenticated_client.get(
        f"/api/v1/users/{memory_user.id}/memories"
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["total_count"] == 3
    assert [m["content_type"] for m in body["memories"]] == [
        "coaching",
        "coaching",
        "pattern",
    ]
    assert "openings?" in body["memories"][0]["content_text"]
    assert "rook endgames?" in body["memories"][1]["content_text"]
    assert "rook endgame technique" in body["memories"][2]["content_text"]
    assert "embedding" not in body["memories"][0]


@pytest.mark.api
def test_list_memories_filters_by_slice(authenticated_client, memory_user, db):
    _seed(db, memory_user)

    response = authenticated_client.get(
        f"/api/v1/users/{memory_user.id}/memories",
        params={"content_type": "pattern"},
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["total_count"] == 1
    assert body["memories"][0]["content_type"] == "pattern"


@pytest.mark.api
def test_list_memories_paginates(authenticated_client, memory_user, db):
    _seed(db, memory_user)

    response = authenticated_client.get(
        f"/api/v1/users/{memory_user.id}/memories",
        params={"limit": 2, "offset": 0},
    )
    page_one = response.json()
    assert page_one["total_count"] == 3
    assert len(page_one["memories"]) == 2

    response = authenticated_client.get(
        f"/api/v1/users/{memory_user.id}/memories",
        params={"limit": 2, "offset": 2},
    )
    page_two = response.json()
    assert len(page_two["memories"]) == 1
    assert page_two["memories"][0]["id"] not in {
        m["id"] for m in page_one["memories"]
    }


@pytest.mark.api
def test_list_memories_empty_for_new_user(authenticated_client, memory_user):
    response = authenticated_client.get(
        f"/api/v1/users/{memory_user.id}/memories"
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["total_count"] == 0
    assert body["memories"] == []


@pytest.mark.api
def test_list_memories_forbidden_for_other_user(
    client, memory_user, other_user, db
):
    _seed(db, memory_user)

    async def override_get_current_user():
        return other_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        response = client.get(f"/api/v1/users/{memory_user.id}/memories")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == status.HTTP_403_FORBIDDEN
