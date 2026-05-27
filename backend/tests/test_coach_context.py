"""Tests for coach context assembly (P1-CM-02)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.pattern import PlayerPattern
from app.models.profile import PlayerProfile
from app.models.user import User
from app.services.chat.chess_coach import ChessCoach
from app.services.chat.context_assembler import assemble_coach_context
from app.services.chat import ChatIntent


@pytest.fixture
def coach_user(db):
    user = User(
        email="coach-context@example.com",
        supabase_user_id="coach-context-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_profile(db, user: User) -> PlayerProfile:
    now = datetime.now(timezone.utc)
    row = PlayerProfile(
        user_id=user.id,
        profile_version=3,
        snapshot_at=now,
        archetype="Tactician",
        primary_weaknesses=["Endgame technique", "Time pressure"],
        phase_performance={"opening": 22.0, "middlegame": 28.0, "endgame": 35.0},
        games_analyzed_count=15,
        patterns_detected_count=2,
        generated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _create_pattern(
    db,
    user: User,
    *,
    pattern_type: str = "phase",
    pattern_subtype: str = "endgame",
    severity: str,
    confidence: float,
    description: str,
) -> PlayerPattern:
    row = PlayerPattern(
        user_id=user.id,
        pattern_type=pattern_type,
        pattern_subtype=pattern_subtype,
        severity=severity,
        confidence_score=confidence,
        occurrence_count=5,
        affected_games_count=4,
        affected_games_ratio=0.4,
        pattern_description=description,
        is_strength=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_assemble_coach_context_includes_profile_and_patterns(db, coach_user):
    profile = _create_profile(db, coach_user)
    low = _create_pattern(
        db,
        coach_user,
        pattern_subtype="opening",
        severity="low",
        confidence=0.5,
        description="Minor opening inaccuracy",
    )
    critical = _create_pattern(
        db,
        coach_user,
        pattern_subtype="endgame",
        severity="critical",
        confidence=0.9,
        description="Rook endgame conversion failures",
    )

    context = assemble_coach_context(db, coach_user.id, top_patterns=5)

    assert f"profile_version: {profile.profile_version}" in context
    assert f"games_analyzed_count: {profile.games_analyzed_count}" in context
    assert "Endgame technique" in context
    assert "opening: 22.0" in context
    assert f"pattern_id={critical.id}" in context
    assert "Rook endgame conversion failures" in context
    assert critical.id != low.id
    assert context.index(f"pattern_id={critical.id}") < context.index(
        f"pattern_id={low.id}"
    )


def test_assemble_coach_context_handles_missing_profile(db, coach_user):
    _create_pattern(
        db,
        coach_user,
        severity="medium",
        confidence=0.7,
        description="Middlegame hanging pieces",
    )

    context = assemble_coach_context(db, coach_user.id)

    assert "insufficient analyzed games" in context.lower()
    assert "pattern_id=" in context


def test_assemble_coach_context_empty_user_has_no_data(db, coach_user):
    context = assemble_coach_context(db, coach_user.id)

    assert "insufficient analyzed games" in context.lower()
    assert "none persisted yet" in context.lower()


@pytest.mark.asyncio
async def test_general_question_injects_context_without_llm(db, coach_user):
    _create_profile(db, coach_user)
    coach = ChessCoach()

    response = await coach.process_message(
        message="How can I improve my endgames?",
        user_id=coach_user.id,
        db=db,
    )

    assert response.intent == ChatIntent.GENERAL_QUESTION
    assert "profile_version: 3" in response.message
    assert "Personalized context from your games" in response.message


@pytest.mark.asyncio
async def test_general_question_uses_llm_system_prompt_when_available(db, coach_user):
    _create_profile(db, coach_user)
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(
        return_value={"content": "Focus on rook endgames based on your profile."}
    )
    coach = ChessCoach(ai_client=mock_client)

    response = await coach.process_message(
        message="How can I improve?",
        user_id=coach_user.id,
        db=db,
    )

    assert "rook endgames" in response.message.lower()
    mock_client.chat_completion.assert_awaited_once()
    messages = mock_client.chat_completion.await_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert "profile_version: 3" in messages[0]["content"]
    assert messages[1]["role"] == "user"
