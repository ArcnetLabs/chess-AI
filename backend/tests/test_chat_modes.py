"""Tests for chat session modes and the interview extraction flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest  # noqa: F401  (pytest fixtures)

from app.services.chat import ChatContext, ChatMessage, MessageRole
from app.services.chat.chess_coach import ChessCoach
from app.services.chat.session_store import deserialize_context, serialize_context
from app.services.coaching.chat_memory_service import (
    build_interview_memory_text,
    content_id_for_exchange,
    content_id_for_interview_summary,
)

INTERVIEW_SUMMARY_BLOCK = (
    "\n[INTERVIEW_SUMMARY]\n"
    "Goal: 1800 rapid\n"
    "Weaknesses: rook endgames, time management\n"
    "Time budget: 5 hours per week\n"
    "Openings: Italian, Caro-Kann"
)


def _interview_context(session_id: str = "s-int") -> ChatContext:
    context = ChatContext(session_id=session_id, user_id=1, mode="interview")
    context.add_message(
        ChatMessage(role=MessageRole.USER, content="Aiming for 1800 rapid.")
    )
    return context


def test_mode_validation():
    try:
        ChatContext(session_id="s", user_id=1, mode="bogus")
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown mode")


def test_mode_round_trips_through_store():
    context = _interview_context()
    context.interview_summary = "Goal: 1800"
    restored = deserialize_context(serialize_context(context))
    assert restored.mode == "interview"
    assert restored.interview_summary == "Goal: 1800"
    plain = deserialize_context(serialize_context(ChatContext(session_id="s2")))
    assert plain.mode == "coach"


async def test_interview_reply_strips_marker_and_sets_focus_areas():
    mock_client = AsyncMock()
    mock_client.chat_completion = AsyncMock(
        side_effect=[
            {
                "content": (
                    "Great — 1800 is a solid target. Last question: which "
                    "openings do you play?"
                ),
                "provider": "local",
            },
            {
                "content": (
                    "Got it, that completes the picture. Here is your baseline."
                    + INTERVIEW_SUMMARY_BLOCK
                ),
                "provider": "local",
            },
        ]
    )
    coach = ChessCoach(ai_client=mock_client)
    context = _interview_context()

    first = await coach._llm_coach_reply("1800", context, "grounding")
    assert "[INTERVIEW_SUMMARY]" not in first["content"]
    assert context.interview_summary == ""

    second = await coach._llm_coach_reply(
        "Italian and Caro-Kann, 5 hours a week", context, "grounding"
    )
    assert "[INTERVIEW_SUMMARY]" not in second["content"]
    assert "1800" in context.interview_summary
    lowered = [area.lower() for area in context.focus_areas]
    assert "rook endgames" in lowered
    assert "time management" in lowered


async def test_interview_prompt_only_in_interview_mode():
    mock_client = AsyncMock()
    mock_client.chat_completion = AsyncMock(
        return_value={"content": "ok", "provider": "local"}
    )
    coach = ChessCoach(ai_client=mock_client)

    context = _interview_context()
    await coach._llm_coach_reply("answer", context, "grounding")
    interview_system = mock_client.chat_completion.await_args_list[-1].kwargs[
        "messages"
    ][0]["content"]
    assert "Interview mode" in interview_system
    assert "[INTERVIEW_SUMMARY]" in interview_system

    coach_context = ChatContext(session_id="s-coach", user_id=1, mode="coach")
    await coach._llm_coach_reply("hello", coach_context, "grounding")
    coach_system = mock_client.chat_completion.await_args_list[-1].kwargs[
        "messages"
    ][0]["content"]
    assert "Interview mode" not in coach_system


async def test_analyze_prompt_only_in_analyze_mode():
    mock_client = AsyncMock()
    mock_client.chat_completion = AsyncMock(
        return_value={"content": "ok", "provider": "local"}
    )
    coach = ChessCoach(ai_client=mock_client)

    analyze_context = ChatContext(session_id="s-an", user_id=1, mode="analyze")
    await coach._llm_coach_reply("Evaluate this position", analyze_context, "grounding")
    analyze_system = mock_client.chat_completion.await_args_list[-1].kwargs[
        "messages"
    ][0]["content"]
    assert "Analyze-mode session" in analyze_system
    assert "never estimate" in analyze_system.lower()

    coach_context = ChatContext(session_id="s-coach2", user_id=1, mode="coach")
    await coach._llm_coach_reply("hello", coach_context, "grounding")
    coach_system = mock_client.chat_completion.await_args_list[-1].kwargs[
        "messages"
    ][0]["content"]
    assert "Analyze-mode session" not in coach_system
    interview_context = _interview_context()
    await coach._llm_coach_reply("1800", interview_context, "grounding")
    interview_system = mock_client.chat_completion.await_args_list[-1].kwargs[
        "messages"
    ][0]["content"]
    assert "Analyze-mode session" not in interview_system


async def test_no_marker_leaves_context_untouched():
    mock_client = AsyncMock()
    mock_client.chat_completion = AsyncMock(
        return_value={
            "content": "What is your time budget per week?",
            "provider": "local",
        }
    )
    coach = ChessCoach(ai_client=mock_client)
    context = _interview_context()

    await coach._llm_coach_reply("question?", context, "grounding")
    assert context.interview_summary == ""
    assert context.focus_areas == []


async def test_mode_from_api_session_creation(db, client, monkeypatch):
    """POST /chat/session with mode=interview persists the mode."""
    from app.__main__ import app
    from app.middleware.auth_middleware import get_current_user
    from app.models.user import User

    user = User(
        email="modes-api@example.com",
        supabase_user_id="modes-api-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        response = client.post(
            "/api/v1/chat/session", json={"mode": "interview"}
        )
        listed = client.get("/api/v1/chat/sessions")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["context"]["mode"] == "interview"
    assert "baseline" in body["message"].lower()

    modes = [s["mode"] for s in listed.json()["sessions"]]
    assert "interview" in modes


def test_interview_memory_text_and_unique_ids():
    text = build_interview_memory_text(
        "Goal: 1800 rapid\nWeaknesses: rook endgames"
    )
    assert text.startswith("Interview summary (")
    assert "Goal: 1800 rapid" in text
    ids = {
        content_id_for_interview_summary("s1"),
        content_id_for_exchange("s1", 0),
        content_id_for_interview_summary("s2"),
    }
    assert len(ids) == 3
