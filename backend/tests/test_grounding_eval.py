"""Tests for coach context grounding evaluation (P3-CM-05)."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.models.pattern import PlayerPattern
from app.models.profile import PlayerProfile
from app.models.user import User
from app.services.coaching.grounding_eval_service import (
    GroundingEvalCase,
    GroundingExpectation,
    evaluate_coach_context,
    load_grounding_eval_set,
    score_context_grounding,
)


@pytest.fixture
def eval_user(db):
    user = User(
        email="grounding-eval@example.com",
        supabase_user_id="grounding-eval-sub",
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
        profile_version=4,
        snapshot_at=now,
        archetype="Tactician",
        primary_weaknesses=["Endgame technique", "Time pressure"],
        phase_performance={"opening": 22.0, "middlegame": 28.0, "endgame": 35.0},
        games_analyzed_count=20,
        patterns_detected_count=10,
        profile_summary="Aggressive tactician with endgame conversion issues.",
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
    pattern_subtype: str,
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


def _seed_grounding_fixtures(db, user: User) -> None:
    """Seed profile and patterns aligned with eval case expectations."""
    _create_profile(db, user)
    fixtures = [
        ("endgame", "critical", 0.95, "Rook endgame conversion failures under time pressure"),
        ("opening", "high", 0.85, "Opening inaccuracies in the first 15 moves"),
        ("high_opening_acpl", "high", 0.82, "High opening ACPL across rapid games"),
        ("middlegame", "medium", 0.78, "Hanging pieces in complex middlegame positions"),
        ("high_middlegame_acpl", "medium", 0.75, "Elevated middlegame ACPL with tactical misses"),
        ("fork_miss", "high", 0.88, "Missed fork tactics in middlegame calculation"),
        ("trap_falls", "medium", 0.7, "Falls for opening traps too often"),
        ("high_blunder_rate", "critical", 0.92, "High blunder rate especially under time pressure"),
        ("middlegame_major_swings", "high", 0.8, "Major evaluation swings from middlegame blunders"),
        ("sicilian_defense", "medium", 0.72, "Sicilian Defense structural weaknesses"),
        ("high_endgame_acpl", "high", 0.86, "High endgame ACPL on pawn endgame technique"),
    ]
    for subtype, severity, confidence, description in fixtures:
        _create_pattern(
            db,
            user,
            pattern_subtype=subtype,
            severity=severity,
            confidence=confidence,
            description=description,
        )


def test_load_grounding_eval_set_has_fifty_cases():
    cases = load_grounding_eval_set()
    assert len(cases) == 50
    assert cases[0].id == "ge-001"
    assert cases[-1].id == "ge-050"
    assert all(isinstance(case, GroundingEvalCase) for case in cases)
    assert all(case.question for case in cases)


def test_score_context_grounding_passes_when_all_expectations_met():
    context = (
        "profile_version: 4\n"
        "archetype: Tactician\n"
        "type=phase/endgame severity=critical: Rook endgame conversion failures\n"
    )
    expected = GroundingExpectation(
        pattern_subtypes=("endgame",),
        keywords=("rook", "endgame"),
        require_profile=True,
    )
    assert score_context_grounding(context, expected) is True


def test_score_context_grounding_fails_on_missing_subtype():
    context = "type=phase/opening severity=high: Opening issues"
    expected = GroundingExpectation(pattern_subtypes=("endgame",))
    assert score_context_grounding(context, expected) is False


def test_score_context_grounding_fails_on_missing_keyword():
    context = "type=phase/endgame: Generic endgame weakness"
    expected = GroundingExpectation(keywords=("rook",))
    assert score_context_grounding(context, expected) is False


def test_score_context_grounding_fails_when_profile_required_but_missing():
    context = "Detected patterns: none persisted yet."
    expected = GroundingExpectation(require_profile=True)
    assert score_context_grounding(context, expected) is False


def test_score_context_grounding_passes_generic_question_with_no_expectations():
    context = "## Player Context\nDo not invent chess evaluations."
    expected = GroundingExpectation()
    assert score_context_grounding(context, expected) is True


@patch("app.services.chat.context_assembler.retrieve_semantic_memories", return_value=[])
def test_evaluate_coach_context_scores_seeded_user(mock_retrieve, db, eval_user):
    _seed_grounding_fixtures(db, eval_user)
    all_cases = load_grounding_eval_set()

    subset_ids = {
        "ge-001",
        "ge-006",
        "ge-011",
        "ge-016",
        "ge-023",
        "ge-026",
        "ge-031",
        "ge-041",
        "ge-047",
        "ge-050",
    }
    subset = [case for case in all_cases if case.id in subset_ids]

    result = evaluate_coach_context(db, eval_user.id, subset, top_patterns=15)

    assert result.total == len(subset)
    assert result.pass_count == len(subset)
    assert result.pass_rate == 1.0
    assert all(item.passed for item in result.case_results)
    assert mock_retrieve.call_count == len(subset)


@patch("app.services.chat.context_assembler.retrieve_semantic_memories", return_value=[])
def test_evaluate_coach_context_pass_rate_computation(mock_retrieve, db, eval_user):
    _seed_grounding_fixtures(db, eval_user)
    all_cases = load_grounding_eval_set()

    passing = next(case for case in all_cases if case.id == "ge-001")
    failing = GroundingEvalCase(
        id="ge-fail",
        question="Why do I lose queen endgames?",
        expected=GroundingExpectation(
            pattern_subtypes=("queen_endgame",),
            keywords=("queen endgame",),
        ),
    )

    result = evaluate_coach_context(db, eval_user.id, [passing, failing])

    assert result.total == 2
    assert result.pass_count == 1
    assert result.pass_rate == 0.5
    by_id = {item.case_id: item.passed for item in result.case_results}
    assert by_id["ge-001"] is True
    assert by_id["ge-fail"] is False


@patch("app.services.chat.context_assembler.retrieve_semantic_memories", return_value=[])
def test_evaluate_coach_context_empty_user_fails_profile_cases(
    mock_retrieve, db, eval_user
):
    all_cases = load_grounding_eval_set()
    profile_cases = [case for case in all_cases if case.expected.require_profile][:5]

    result = evaluate_coach_context(db, eval_user.id, profile_cases)

    assert result.pass_count == 0
    assert result.pass_rate == 0.0
    assert all(not item.passed for item in result.case_results)


@patch("app.services.chat.context_assembler.retrieve_semantic_memories", return_value=[])
def test_evaluate_coach_context_full_set_meets_phase3_exit_gate(
    mock_retrieve, db, eval_user
):
    """Phase 3 exit gate: >=90% pass rate on the full 50-case grounding eval set."""
    _seed_grounding_fixtures(db, eval_user)
    all_cases = load_grounding_eval_set()

    result = evaluate_coach_context(db, eval_user.id, all_cases, top_patterns=15)
    failed = [item for item in result.case_results if not item.passed]

    assert result.pass_rate >= 0.9, (
        f"pass_rate {result.pass_rate:.1%} ({result.pass_count}/{result.total}); "
        f"failed ids: {[item.case_id for item in failed]}"
    )
