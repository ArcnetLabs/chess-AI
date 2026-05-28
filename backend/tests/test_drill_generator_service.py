"""Tests for pattern-driven drill generator (P3-TR-02)."""

from datetime import datetime, timezone

from app.models.game import Game
from app.models.pattern import PatternOccurrence, PlayerPattern
from app.models.training import DrillAttempt, TrainingPlan
from app.models.user import User
from app.services.training.drill_generator_service import (
    generate_training_plan,
    get_next_plan_version,
    select_patterns_for_drills,
)


def _create_user(db, **overrides) -> User:
    user = User(
        email=overrides.get("email", "drill-gen@example.com"),
        supabase_user_id=overrides.get("supabase_user_id", "drill-gen-sub"),
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_game(db, user: User, *, suffix: str = "1") -> Game:
    game = Game(
        user_id=user.id,
        chesscom_game_id=f"drill-gen-game-{user.id}-{suffix}",
        white_username="drill_user",
        black_username="opponent",
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


def _create_pattern(db, user: User, **overrides) -> PlayerPattern:
    now = datetime.now(timezone.utc)
    row = PlayerPattern(
        user_id=user.id,
        pattern_type=overrides.get("pattern_type", "phase_weakness"),
        pattern_subtype=overrides.get("pattern_subtype", "high_endgame_acpl"),
        severity=overrides.get("severity", "medium"),
        confidence_score=overrides.get("confidence_score", 0.7),
        occurrence_count=overrides.get("occurrence_count", 3),
        affected_games_count=overrides.get("affected_games_count", 3),
        affected_games_ratio=overrides.get("affected_games_ratio", 0.3),
        pattern_description=overrides.get(
            "pattern_description",
            "Endgame technique needs work.",
        ),
        example_positions=overrides.get(
            "example_positions",
            ["8/8/8/8/8/4k3/8/4K3 w - - 0 1"],
        ),
        first_seen_at=now,
        last_seen_at=now,
        is_strength=overrides.get("is_strength", False),
        recommended_drill_type=overrides.get("recommended_drill_type"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _create_occurrence(
    db,
    user: User,
    pattern: PlayerPattern,
    game: Game,
    **overrides,
) -> PatternOccurrence:
    row = PatternOccurrence(
        pattern_id=pattern.id,
        user_id=user.id,
        game_id=game.id,
        move_number=overrides.get("move_number", 40),
        game_phase=overrides.get("game_phase", "endgame"),
        fen_before=overrides.get(
            "fen_before",
            "8/8/8/8/8/4k3/8/4K3 w - - 0 1",
        ),
        best_move=overrides.get("best_move", "Ke2"),
        context_description=overrides.get(
            "context_description",
            "King activity in a basic king-and-pawn endgame.",
        ),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class TestGenerateTrainingPlan:
    def test_returns_none_when_no_patterns(self, db):
        user = _create_user(db)

        plan = generate_training_plan(db, user.id)

        assert plan is None
        assert db.query(TrainingPlan).count() == 0

    def test_skips_strength_patterns(self, db):
        user = _create_user(db)
        _create_pattern(
            db,
            user,
            pattern_subtype="high_opening_acpl",
            is_strength=True,
            severity="critical",
            confidence_score=0.99,
            pattern_description="Excellent opening preparation.",
        )
        weakness = _create_pattern(
            db,
            user,
            pattern_subtype="high_endgame_acpl",
            severity="medium",
            confidence_score=0.6,
            pattern_description="Weak endgame technique.",
        )

        selected = select_patterns_for_drills(db, user.id, limit=5)

        assert len(selected) == 1
        assert selected[0].id == weakness.id

    def test_plan_version_increments_on_second_plan(self, db):
        user = _create_user(db)
        _create_pattern(db, user, severity="high", confidence_score=0.9)

        first = generate_training_plan(db, user.id)
        second = generate_training_plan(db, user.id)

        assert first is not None
        assert second is not None
        assert first.plan_version == 1
        assert second.plan_version == 2
        assert get_next_plan_version(db, user.id) == 3

    def test_creates_drill_attempts_with_prompt_and_drill_type(self, db):
        user = _create_user(db)
        pattern = _create_pattern(
            db,
            user,
            severity="critical",
            confidence_score=0.95,
            recommended_drill_type="endgame_technique",
            pattern_description="Critical endgame inaccuracy pattern.",
        )

        plan = generate_training_plan(db, user.id, max_drills=3)

        assert plan is not None
        assert plan.status == "active"
        assert plan.source == "pattern_engine"
        assert plan.drill_count == 1
        assert plan.focus_pattern_ids == [pattern.id]

        attempts = (
            db.query(DrillAttempt)
            .filter(DrillAttempt.training_plan_id == plan.id)
            .all()
        )
        assert len(attempts) == 1
        attempt = attempts[0]
        assert attempt.pattern_id == pattern.id
        assert attempt.drill_type == "endgame_technique"
        assert attempt.status == "pending"
        assert "Critical endgame inaccuracy" in attempt.prompt_text
        assert attempt.attempt_metadata["pattern_subtype"] == pattern.pattern_subtype

    def test_uses_occurrence_fen_and_best_move(self, db):
        user = _create_user(db)
        game = _create_game(db, user)
        pattern = _create_pattern(
            db,
            user,
            example_positions=["fallback/fen/only"],
            recommended_drill_type=None,
            pattern_subtype="high_endgame_acpl",
        )
        occurrence = _create_occurrence(
            db,
            user,
            pattern,
            game,
            fen_before="8/8/8/8/8/4k3/8/4K3 w - - 0 1",
            best_move="Kd2",
        )

        plan = generate_training_plan(db, user.id)

        attempt = (
            db.query(DrillAttempt)
            .filter(DrillAttempt.training_plan_id == plan.id)
            .one()
        )
        assert attempt.position_fen == occurrence.fen_before
        assert attempt.expected_answer == "Kd2"
        assert "King activity" in attempt.prompt_text

    def test_respects_max_drills_limit(self, db):
        user = _create_user(db)
        _create_pattern(
            db,
            user,
            pattern_subtype="high_opening_acpl",
            severity="critical",
            confidence_score=0.99,
        )
        _create_pattern(
            db,
            user,
            pattern_subtype="high_middlegame_acpl",
            severity="high",
            confidence_score=0.85,
        )
        _create_pattern(
            db,
            user,
            pattern_subtype="high_endgame_acpl",
            severity="medium",
            confidence_score=0.7,
        )

        plan = generate_training_plan(db, user.id, max_drills=2)

        assert plan is not None
        assert plan.drill_count == 2
        assert len(plan.focus_pattern_ids) == 2
        assert db.query(DrillAttempt).filter(
            DrillAttempt.training_plan_id == plan.id
        ).count() == 2
