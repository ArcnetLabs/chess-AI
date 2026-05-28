"""Tests for pattern API routes (P1-PR-06)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status

from app.__main__ import app
from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.pattern import PlayerPattern
from app.models.user import User


@pytest.fixture
def pattern_user(db):
    user = User(
        email="patterns@example.com",
        supabase_user_id="pattern-user-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def other_user(db):
    user = User(
        email="other@example.com",
        supabase_user_id="other-user-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def authenticated_client(client, db, pattern_user):
    async def override_get_current_user():
        return pattern_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def sample_pattern(db, pattern_user):
    now = datetime.now(timezone.utc)
    row = PlayerPattern(
        user_id=pattern_user.id,
        pattern_type="phase_weakness",
        pattern_subtype="high_opening_acpl",
        severity="medium",
        confidence_score=0.72,
        occurrence_count=4,
        affected_games_count=4,
        affected_games_ratio=0.8,
        pattern_description="Opening phase ACPL is elevated across recent games.",
        first_seen_at=now,
        last_seen_at=now,
        is_strength=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.mark.api
def test_trigger_pattern_analysis_queues_celery(authenticated_client, pattern_user):
    mock_task = MagicMock()
    mock_task.id = "celery-task-abc"

    with patch("app.api.patterns.detect_patterns_task.delay", return_value=mock_task):
        response = authenticated_client.post(
            f"/api/v1/users/{pattern_user.id}/patterns/analyze"
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["task_id"] == "celery-task-abc"
    assert "queued" in body["message"].lower()


@pytest.mark.api
def test_get_user_patterns_returns_rows(
    authenticated_client, pattern_user, sample_pattern
):
    response = authenticated_client.get(
        f"/api/v1/users/{pattern_user.id}/patterns"
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert len(body) == 1
    assert body[0]["pattern_type"] == "phase_weakness"
    assert body[0]["pattern_subtype"] == "high_opening_acpl"
    assert body[0]["user_id"] == pattern_user.id


@pytest.mark.api
def test_get_patterns_forbidden_for_other_user(
    client, db, pattern_user, other_user, sample_pattern
):
    async def override_get_current_user():
        return other_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        response = client.get(f"/api/v1/users/{pattern_user.id}/patterns")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.api
def test_trigger_analyze_forbidden_for_other_user(client, db, pattern_user, other_user):
    async def override_get_current_user():
        return other_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        response = client.post(
            f"/api/v1/users/{pattern_user.id}/patterns/analyze"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == status.HTTP_403_FORBIDDEN
