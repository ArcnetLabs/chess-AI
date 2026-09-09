"""Tests for the training plans/drills API (redesign P6)."""

import pytest
from fastapi import status

from app.__main__ import app
from app.middleware.auth_middleware import get_current_user
from app.models.user import User


@pytest.fixture
def training_user(db):
    user = User(
        email="training-api@example.com",
        supabase_user_id="training-api-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def other_user(db):
    user = User(
        email="training-other@example.com",
        supabase_user_id="training-other-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def authenticated_client(client, training_user):
    async def override_get_current_user():
        return training_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


PLAN_BODY = {
    "title": "Endgame conversion bootcamp",
    "source": "interview",
    "focus_areas": ["endgame_technique"],
    "drills": [
        {
            "drill_type": "endgame_technique",
            "prompt_text": "Convert the Lucena position to a win.",
            "position_fen": "8/8/8/8/8/8/8/6K1 w - - 0 1",
        },
        {
            "drill_type": "puzzle",
            "prompt_text": "Find the only move that holds the draw.",
        },
    ],
}


@pytest.mark.api
def test_create_plan_with_drills(authenticated_client, training_user, db):
    response = authenticated_client.post(
        f"/api/v1/training/{training_user.id}/plans", json=PLAN_BODY
    )

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["plan_version"] == 1
    assert body["status"] == "active"
    assert body["source"] == "interview"
    assert body["drill_count"] == 2
    assert body["completed_drill_count"] == 0
    assert [d["status"] for d in body["drills"]] == ["pending", "pending"]
    assert body["focus_areas"] == ["endgame_technique"]


@pytest.mark.api
def test_active_plan_returns_with_drills_and_404_when_absent(
    authenticated_client, training_user
):
    missing = authenticated_client.get(
        f"/api/v1/training/{training_user.id}/plans/active"
    )
    assert missing.status_code == status.HTTP_404_NOT_FOUND

    created = authenticated_client.post(
        f"/api/v1/training/{training_user.id}/plans", json=PLAN_BODY
    )
    assert created.status_code == status.HTTP_201_CREATED

    active = authenticated_client.get(
        f"/api/v1/training/{training_user.id}/plans/active"
    )
    assert active.status_code == status.HTTP_200_OK
    assert active.json()["title"] == "Endgame conversion bootcamp"
    assert len(active.json()["drills"]) == 2


@pytest.mark.api
def test_plan_versions_increment(authenticated_client, training_user):
    first = authenticated_client.post(
        f"/api/v1/training/{training_user.id}/plans", json=PLAN_BODY
    )
    second = authenticated_client.post(
        f"/api/v1/training/{training_user.id}/plans",
        json={**PLAN_BODY, "title": "Round two"},
    )
    assert first.json()["plan_version"] == 1
    assert second.json()["plan_version"] == 2

    listing = authenticated_client.get(
        f"/api/v1/training/{training_user.id}/plans"
    )
    versions = [p["plan_version"] for p in listing.json()["plans"]]
    assert versions == [2, 1]


@pytest.mark.api
def test_adhoc_drill_save_and_completion_syncs_plan(
    authenticated_client, training_user
):
    plan = authenticated_client.post(
        f"/api/v1/training/{training_user.id}/plans", json=PLAN_BODY
    ).json()
    plan_id = plan["id"]

    drill = authenticated_client.post(
        f"/api/v1/training/{training_user.id}/drills",
        json={
            "drill_type": "puzzle",
            "prompt_text": "Save this drill: mate in two.",
            "training_plan_id": plan_id,
        },
    )
    assert drill.status_code == status.HTTP_201_CREATED
    drill_id = drill.json()["id"]

    started = authenticated_client.patch(
        f"/api/v1/training/{training_user.id}/drills/{drill_id}",
        json={"status": "in_progress"},
    )
    assert started.status_code == status.HTTP_200_OK
    assert started.json()["status"] == "in_progress"

    completed = authenticated_client.post(
        f"/api/v1/training/{training_user.id}/drills/{drill_id}/complete",
        json={"user_answer": "Qh7#", "is_correct": True, "score": 1.0},
    )
    assert completed.status_code == status.HTTP_200_OK
    assert completed.json()["status"] == "completed"
    assert completed.json()["is_correct"] is True

    active = authenticated_client.get(
        f"/api/v1/training/{training_user.id}/plans/active"
    )
    assert active.json()["completed_drill_count"] == 1

    progress = authenticated_client.get(
        f"/api/v1/training/{training_user.id}/progress"
    )
    body = progress.json()
    assert body["total_drills"] == 3
    assert body["completed_drills"] == 1
    assert body["active_plan_id"] == plan_id


@pytest.mark.api
def test_invalid_transitions_rejected(authenticated_client, training_user):
    created = authenticated_client.post(
        f"/api/v1/training/{training_user.id}/plans", json=PLAN_BODY
    ).json()
    drill_id = created["drills"][0]["id"]

    bad_status = authenticated_client.patch(
        f"/api/v1/training/{training_user.id}/drills/{drill_id}",
        json={"status": "completed"},
    )
    assert bad_status.status_code == status.HTTP_400_BAD_REQUEST

    completed = authenticated_client.post(
        f"/api/v1/training/{training_user.id}/drills/{drill_id}/complete",
        json={"user_answer": "Rd8", "is_correct": True},
    )
    assert completed.status_code == status.HTTP_200_OK

    again = authenticated_client.post(
        f"/api/v1/training/{training_user.id}/drills/{drill_id}/complete",
        json={"user_answer": "Rd8", "is_correct": True},
    )
    assert again.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.api
def test_training_forbidden_for_other_user(client, training_user, other_user):
    async def override_get_current_user():
        return other_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        response = client.get(f"/api/v1/training/{training_user.id}/plans")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.api
def test_plan_needs_at_least_one_drill(authenticated_client, training_user):
    response = authenticated_client.post(
        f"/api/v1/training/{training_user.id}/plans",
        json={**PLAN_BODY, "drills": []},
    )
    # Rejected at request validation: drills has min_length=1.
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
