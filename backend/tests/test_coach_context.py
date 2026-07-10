"""Tests for coach context assembly (P1-CM-02, P3-CM-04)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.pattern import PlayerPattern
from app.models.profile import PlayerProfile
from app.models.user import User
from app.services.chat.chess_coach import ChessCoach
from app.services.chat.context_assembler import assemble_coach_context
from app.services.chat import ChatIntent
from app.services.coaching.retrieval_service import RetrievedMemory


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
    assert "15 games" in response.message
    assert "endgame" in response.message.lower()
    assert "profile_version" not in response.message


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
    assert mock_client.chat_completion.await_args.kwargs["max_tokens"] == 350


@pytest.mark.asyncio
async def test_rating_goal_uses_grounded_llm_path(db, coach_user):
    _create_profile(db, coach_user)
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(
        return_value={"content": "Your opening phase is the first area to improve."}
    )
    coach = ChessCoach(ai_client=mock_client)

    response = await coach.process_message(
        message="What's holding me back from 1800?",
        user_id=coach_user.id,
        db=db,
    )

    assert response.intent == ChatIntent.GENERAL_QUESTION
    assert response.used_llm is True
    mock_client.chat_completion.assert_awaited_once()


@pytest.mark.asyncio
async def test_general_question_includes_recent_thread_history(db, coach_user):
    _create_profile(db, coach_user)
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(
        side_effect=[
            {"content": "Let's focus on your opening choices."},
            {"content": "That opening pattern is still the priority."},
        ]
    )
    coach = ChessCoach(ai_client=mock_client)

    first = await coach.process_message(
        message="How can I improve my openings?",
        user_id=coach_user.id,
        db=db,
    )
    await coach.process_message(
        message="What should I work on first?",
        session_id=first.session_id,
        user_id=coach_user.id,
        db=db,
    )

    messages = mock_client.chat_completion.await_args_list[1].kwargs["messages"]
    assert messages[1:] == [
        {"role": "user", "content": "How can I improve my openings?"},
        {"role": "assistant", "content": "Let's focus on your opening choices."},
        {"role": "user", "content": "What should I work on first?"},
    ]


def _sample_retrieved_memory() -> RetrievedMemory:
    return RetrievedMemory(
        id=42,
        content_type="coaching",
        content_id=7,
        content_text="User struggles converting rook endgames under time pressure.",
        similarity_score=0.87,
        metadata={"topic": "endgame"},
    )


@patch("app.services.chat.context_assembler.retrieve_semantic_memories")
def test_assemble_coach_context_includes_retrieved_memories(
    mock_retrieve, db, coach_user
):
    _create_profile(db, coach_user)
    mock_retrieve.return_value = [_sample_retrieved_memory()]

    context = assemble_coach_context(
        db, coach_user.id, query_text="How do I improve endgames?"
    )

    mock_retrieve.assert_called_once_with(
        db,
        coach_user.id,
        "How do I improve endgames?",
        content_types=None,
    )
    assert "## Relevant Semantic Memories" in context
    assert "rook endgames under time pressure" in context
    assert "profile_version: 3" in context


@patch("app.services.chat.context_assembler.retrieve_semantic_memories")
def test_assemble_coach_context_omits_memory_section_when_empty(
    mock_retrieve, db, coach_user
):
    _create_profile(db, coach_user)
    mock_retrieve.return_value = []

    context = assemble_coach_context(
        db, coach_user.id, query_text="How do I improve endgames?"
    )

    assert "## Relevant Semantic Memories" not in context
    assert "profile_version: 3" in context


@pytest.mark.asyncio
@patch("app.services.chat.context_assembler.retrieve_semantic_memories_async")
async def test_general_question_system_prompt_includes_semantic_memories(
    mock_retrieve_async, db, coach_user
):
    _create_profile(db, coach_user)
    mock_retrieve_async.return_value = [_sample_retrieved_memory()]

    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(
        return_value={"content": "Practice rook endgames with fewer time controls."}
    )
    coach = ChessCoach(ai_client=mock_client)

    await coach.process_message(
        message="How can I improve my endgames?",
        user_id=coach_user.id,
        db=db,
    )

    mock_retrieve_async.assert_awaited_once_with(
        db,
        coach_user.id,
        "How can I improve my endgames?",
        content_types=["pattern"],
    )
    messages = mock_client.chat_completion.await_args.kwargs["messages"]
    system_prompt = messages[0]["content"]
    assert "## Relevant Semantic Memories" in system_prompt
    assert "rook endgames under time pressure" in system_prompt
    assert "supplemental facts" in system_prompt


def test_extract_pattern_ids_from_context_deduplicates():
    from app.services.chat.context_assembler import extract_pattern_ids_from_context

    context = (
        "- pattern_id=5 type=phase/endgame\n"
        "- pattern_id=5 type=phase/opening\n"
        "- pattern_id=12 type=phase/middlegame\n"
    )
    assert extract_pattern_ids_from_context(context) == [5, 12]


@pytest.mark.asyncio
async def test_general_question_llm_response_includes_citation_metadata(db, coach_user):
    _create_profile(db, coach_user)
    _create_pattern(
        db,
        coach_user,
        pattern_subtype="endgame",
        severity="critical",
        confidence=0.9,
        description="Rook endgame conversion failures",
    )

    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(
        return_value={
            "content": "Work on rook endgame technique.",
            "provider": "mock",
        }
    )
    coach = ChessCoach(ai_client=mock_client)

    response = await coach.process_message(
        message="How can I improve my endgames?",
        user_id=coach_user.id,
        db=db,
    )

    assert response.used_llm is True
    assert response.llm_provider == "mock"
    assert response.llm_model is None
    assert response.retrieval_used is True
    assert response.cited_pattern_ids


@pytest.mark.asyncio
async def test_get_chess_coach_wires_ai_client():
    from app.api.chat import get_chess_coach

    with patch("app.api.chat._coach_instance", None), patch(
        "app.api.chat.get_ai_client", return_value=MagicMock()
    ) as mock_get:
        coach = await get_chess_coach()
        assert coach.ai_client is mock_get.return_value


@pytest.mark.asyncio
async def test_get_chess_coach_survives_ai_client_init_failure():
    from app.api.chat import get_chess_coach

    with patch("app.api.chat._coach_instance", None), patch(
        "app.api.chat.get_ai_client", side_effect=RuntimeError("no keys")
    ):
        coach = await get_chess_coach()
        assert coach.ai_client is None
