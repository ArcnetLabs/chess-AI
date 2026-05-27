"""Tests for deterministic profile builder (P1-PP-01)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.game import Game, GameAnalysis
from app.models.pattern import PlayerPattern
from app.models.profile import PlayerProfile
from app.models.user import User
from app.services.profiles.profile_builder import MIN_GAMES_FOR_PROFILE, build_player_profile


def _create_user(db, **overrides) -> User:
    user = User(
        email=overrides.get("email", "profile@example.com"),
        supabase_user_id=overrides.get("supabase_user_id", "profile-user-sub"),
        connection_type="username_only",
        current_ratings=overrides.get(
            "current_ratings",
            {"rapid": 1500, "blitz": 1450},
        ),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_analyzed_game(
    db,
    user: User,
    *,
    game_index: int,
    opening_name: str = "Sicilian Defense",
    opening_acpl: float = 25.0,
    middlegame_acpl: float = 30.0,
    endgame_acpl: float = 35.0,
    user_acpl: float = 28.0,
    end_time: datetime | None = None,
) -> tuple[Game, GameAnalysis]:
    played_at = end_time or datetime.now(timezone.utc) - timedelta(days=game_index)
    game = Game(
        user_id=user.id,
        chesscom_game_id=f"profile-game-{user.id}-{game_index}",
        white_username="profile_user",
        black_username="opponent",
        is_analyzed=True,
        end_time=played_at,
    )
    db.add(game)
    db.flush()

    analysis = GameAnalysis(
        game_id=game.id,
        user_color="white",
        user_acpl=user_acpl,
        opponent_acpl=32.0,
        accuracy_percentage=82.0,
        opening_acpl=opening_acpl,
        middlegame_acpl=middlegame_acpl,
        endgame_acpl=endgame_acpl,
        opening_name=opening_name,
        opening_eco="B90",
        brilliant_moves=1,
        great_moves=2,
        best_moves=5,
        excellent_moves=4,
        good_moves=6,
        inaccuracies=3,
        mistakes=2,
        blunders=1,
    )
    db.add(analysis)
    db.commit()
    db.refresh(game)
    db.refresh(analysis)
    return game, analysis


def _seed_games(db, user: User, count: int, **kwargs) -> None:
    for index in range(count):
        _create_analyzed_game(db, user, game_index=index, **kwargs)


def _create_pattern(db, user: User, **overrides) -> PlayerPattern:
    now = datetime.now(timezone.utc)
    row = PlayerPattern(
        user_id=user.id,
        pattern_type=overrides.get("pattern_type", "phase_weakness"),
        pattern_subtype=overrides.get("pattern_subtype", "high_opening_acpl"),
        severity=overrides.get("severity", "high"),
        confidence_score=overrides.get("confidence_score", 0.85),
        occurrence_count=overrides.get("occurrence_count", 4),
        affected_games_count=overrides.get("affected_games_count", 4),
        affected_games_ratio=overrides.get("affected_games_ratio", 0.4),
        pattern_description=overrides.get(
            "pattern_description",
            "Opening phase ACPL is elevated across recent games.",
        ),
        first_seen_at=now,
        last_seen_at=now,
        is_strength=overrides.get("is_strength", False),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class TestBuildPlayerProfileGate:
    def test_returns_none_when_insufficient_games(self, db):
        user = _create_user(db)
        _seed_games(db, user, MIN_GAMES_FOR_PROFILE - 1)

        profile = build_player_profile(db, user.id)

        assert profile is None
        assert db.query(PlayerProfile).count() == 0

    def test_returns_none_for_unknown_user(self, db):
        profile = build_player_profile(db, 99999)
        assert profile is None


class TestBuildPlayerProfileSnapshot:
    def test_creates_first_snapshot_with_expected_counts(self, db):
        user = _create_user(db)
        _seed_games(db, user, MIN_GAMES_FOR_PROFILE)
        _create_pattern(db, user)

        profile = build_player_profile(db, user.id)

        assert profile is not None
        assert profile.user_id == user.id
        assert profile.profile_version == 1
        assert profile.games_analyzed_count == MIN_GAMES_FOR_PROFILE
        assert profile.patterns_detected_count == 1
        assert profile.profile_summary is None
        assert profile.first_game_date is not None
        assert profile.period_start is not None
        assert profile.period_end is not None
        assert profile.generated_at is not None

    def test_append_only_increments_profile_version(self, db):
        user = _create_user(db)
        _seed_games(db, user, MIN_GAMES_FOR_PROFILE)

        first = build_player_profile(db, user.id)
        second = build_player_profile(db, user.id)

        assert first is not None
        assert second is not None
        assert first.profile_version == 1
        assert second.profile_version == 2
        assert db.query(PlayerProfile).filter(PlayerProfile.user_id == user.id).count() == 2

    def test_populates_pattern_summary_refs(self, db):
        user = _create_user(db)
        _seed_games(db, user, MIN_GAMES_FOR_PROFILE)
        pattern = _create_pattern(db, user, severity="critical", confidence_score=0.95)

        profile = build_player_profile(db, user.id)

        assert profile.pattern_summary_refs
        ref = profile.pattern_summary_refs[0]
        assert ref["pattern_id"] == pattern.id
        assert ref["severity"] == "critical"
        assert ref["confidence"] == 0.95

    def test_populates_phase_performance_from_analysis(self, db):
        user = _create_user(db)
        _seed_games(db, user, MIN_GAMES_FOR_PROFILE, opening_acpl=20.0)

        profile = build_player_profile(db, user.id)

        assert "opening" in profile.phase_performance
        assert "middlegame" in profile.phase_performance
        assert "endgame" in profile.phase_performance
        assert profile.phase_performance["opening"] >= profile.phase_performance["endgame"]

    def test_opening_repertoire_uses_opening_acpl_not_user_acpl(self, db):
        user = _create_user(db)
        for index in range(MIN_GAMES_FOR_PROFILE):
            _create_analyzed_game(
                db,
                user,
                game_index=index,
                opening_name="French Defense",
                opening_acpl=55.0,
                user_acpl=15.0,
            )

        profile = build_player_profile(db, user.id)

        assert "French Defense" in profile.opening_repertoire["problematic"]
        assert profile.opening_repertoire["successful"] == []

    def test_rating_trends_include_current_ratings(self, db):
        user = _create_user(
            db,
            current_ratings={"rapid": 1620, "bullet": 1400},
        )
        _seed_games(db, user, MIN_GAMES_FOR_PROFILE)

        profile = build_player_profile(db, user.id)

        assert profile.rating_trends["current"]["rapid"] == 1620
        assert profile.rating_trends["current"]["bullet"] == 1400

    def test_primary_weaknesses_include_detected_patterns(self, db):
        user = _create_user(db)
        _seed_games(db, user, MIN_GAMES_FOR_PROFILE)
        _create_pattern(
            db,
            user,
            pattern_description="Recurring endgame inaccuracies detected.",
        )

        profile = build_player_profile(db, user.id)

        assert any(
            "endgame inaccuracies" in item.lower()
            for item in profile.primary_weaknesses
        )

    def test_archetype_is_deterministic_string(self, db):
        user = _create_user(db)
        for index in range(MIN_GAMES_FOR_PROFILE):
            _create_analyzed_game(
                db,
                user,
                game_index=index,
                opening_acpl=15.0,
                middlegame_acpl=45.0,
                endgame_acpl=55.0,
            )

        profile = build_player_profile(db, user.id)

        assert profile.archetype == "Strong Opening / Weak Endgame"
