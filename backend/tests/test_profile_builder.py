"""Tests for deterministic profile builder (P1-PP-01)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.game import Game, GameAnalysis
from app.models.pattern import PlayerPattern
from app.models.profile import PlayerProfile
from app.models.user import User
from app.services.profiles.profile_builder import (
    MIN_GAMES_FOR_PROFILE,
    REPERTOIRE_DEPTH_PLIES,
    REPERTOIRE_MIN_GAMES,
    build_player_profile,
)


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
        # Was missing, so a test could pass `evidence=` and have it silently
        # dropped — which made the pattern-link test assert against nothing.
        evidence=overrides.get("evidence"),
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
        assert profile.profile_summary is not None
        assert f"{MIN_GAMES_FOR_PROFILE} analyzed games" in profile.profile_summary
        # The headline states the phase ranking as a comparison, not as a verdict
        # about either phase: see TestTheSummaryNeverCallsOnePhaseBothWays.
        assert (
            "Compared with your other phases" in profile.profile_summary
            or "Where you hold up" in profile.profile_summary
            or "Where it costs you" in profile.profile_summary
            or "No dominant" in profile.profile_summary
        )
        # Card-scale copy: the insights card renders this as its headline.
        assert len(profile.profile_summary) < 400
        assert profile.first_game_date is not None
        assert profile.period_start is not None
        assert profile.period_end is not None
        assert profile.generated_at is not None

    def test_append_only_increments_profile_version(self, db):
        user = _create_user(db)
        _seed_games(db, user, MIN_GAMES_FOR_PROFILE)

        first = build_player_profile(db, user.id)
        # An unchanged rebuild must NOT append a duplicate snapshot — analysis
        # batches fire one build per detection run, which previously produced a
        # dozen identical 200-game aggregations per import.
        repeated = build_player_profile(db, user.id)
        assert repeated is not None
        assert repeated.profile_version == first.profile_version
        assert db.query(PlayerProfile).filter(PlayerProfile.user_id == user.id).count() == 1

        # A real change (more analyzed games) appends the next version.
        _create_analyzed_game(db, user, game_index=9001)
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

        assert profile.archetype == "Least Costly Opening / Costliest Endgame"


def _add_opening_moves(
    db,
    game: Game,
    *,
    structure_key: str,
    colour: str = "white",
    errors: int = 0,
    quiet: int = 6,
    start_ply: int = 1,
) -> None:
    """Opening-phase plies for one game, with the structure reached by the end."""
    from app.models.game_move import GameMove

    ply = start_ply
    for index in range(quiet):
        db.add(
            GameMove(
                user_id=game.user_id,
                game_id=game.id,
                ply=ply,
                move_number=(ply + 1) // 2,
                color=colour,
                is_user_move=True,
                fen_before="8/8/8/8/8/8/8/8 w - - 0 1",
                fen_after="8/8/8/8/8/8/8/8 w - - 0 1",
                position_key=f"pos-{game.id}-{ply}",
                # The last opening ply carries the structure the player settled into.
                structure_key=structure_key,
                move_uci="e2e4",
                best_move_uci="e2e4",
                eval_before_cp=20.0,
                eval_after_cp=10.0,
                cp_loss=10.0,
                classification="blunder" if index < errors else "good",
                phase="opening",
                features={},
            )
        )
        ply += 2
    db.commit()


def _set_first_moves(db, game: Game, moves: str) -> None:
    """Write a specific opening move sequence for a game.

    Used to make a repertoire either repeat or scatter, which is what the stability
    measurement is about.
    """
    from app.models.game_move import GameMove

    for offset, uci in enumerate(moves.split(), start=1):
        db.add(
            GameMove(
                user_id=game.user_id,
                game_id=game.id,
                ply=offset,
                move_number=(offset + 1) // 2,
                color="white" if offset % 2 == 1 else "black",
                is_user_move=offset % 2 == 1,
                fen_before="8/8/8/8/8/8/8/8 w - - 0 1",
                fen_after="8/8/8/8/8/8/8/8 w - - 0 1",
                position_key=f"line-{game.id}-{offset}",
                structure_key="chain",
                move_uci=uci,
                best_move_uci=uci,
                eval_before_cp=20.0,
                eval_after_cp=15.0,
                cp_loss=5.0,
                classification="good",
                phase="opening",
                features={},
            )
        )
    db.commit()


class TestOpeningStructures:
    """Openings keyed by the structure reached, not by opening name.

    The name view is kept for compatibility, but it is not actionable: one name
    covers several structures with different plans, and one structure arrives from
    several names. These tests pin that the structure view groups by the position
    the player actually has to play.
    """

    def test_groups_by_structure_not_by_name(self, db):
        """Both halves of the claim: one name, two structures; two names, one structure."""
        user = _create_user(db)
        total = MIN_GAMES_FOR_PROFILE
        for index in range(total):
            # Two games arrive at a different structure; one of the shared-structure
            # games carries a different opening name.
            structure = "isolated" if index >= total - 2 else "chain"
            name = "Sicilian Defense" if index == 0 else "French Defense"
            game, _ = _create_analyzed_game(
                db, user, game_index=index, opening_name=name, opening_acpl=20.0
            )
            _add_opening_moves(db, game, structure_key=structure)

        profile = build_player_profile(db, user.id)
        structures = profile.opening_repertoire["by_structure"]["structures"]
        by_key = {entry["structure_key"]: entry for entry in structures}

        assert set(by_key) == {"chain", "isolated"}
        # Two different opening names, one structure.
        assert by_key["chain"]["games"] == total - 2
        assert set(by_key["chain"]["opening_names"]) == {"French Defense", "Sicilian Defense"}
        # One opening name, two structures — which is why the name is not the key.
        assert by_key["isolated"]["games"] == 2
        assert by_key["isolated"]["opening_names"] == ["French Defense"]
        assert profile.opening_repertoire["by_structure"]["method"] == "structure_key"

    def test_reports_error_rate_and_score_from_stored_rows(self, db):
        user = _create_user(db)
        game, _ = _create_analyzed_game(db, user, game_index=0, opening_acpl=20.0)
        game.winner = "white"
        _add_opening_moves(db, game, structure_key="chain", colour="white", errors=2, quiet=8)
        for index in range(1, MIN_GAMES_FOR_PROFILE):
            _create_analyzed_game(db, user, game_index=index, opening_acpl=20.0)

        profile = build_player_profile(db, user.id)
        entry = [
            item
            for item in profile.opening_repertoire["by_structure"]["structures"]
            if item["structure_key"] == "chain"
        ][0]

        assert entry["user_moves"] == 8
        assert entry["opening_errors"] == 2
        assert entry["error_rate"] == 0.25
        # The player was White and White won.
        assert entry["score_rate"] == 1.0

    def test_thin_samples_are_flagged_not_hidden(self, db):
        user = _create_user(db)
        game, _ = _create_analyzed_game(db, user, game_index=0, opening_acpl=20.0)
        _add_opening_moves(db, game, structure_key="rare-structure")
        for index in range(1, MIN_GAMES_FOR_PROFILE):
            _create_analyzed_game(db, user, game_index=index, opening_acpl=20.0)

        profile = build_player_profile(db, user.id)
        entry = [
            item
            for item in profile.opening_repertoire["by_structure"]["structures"]
            if item["structure_key"] == "rare-structure"
        ][0]

        assert entry["sample_sufficient"] is False

    def test_links_only_patterns_that_actually_fired_there(self, db):
        user = _create_user(db)
        game, _ = _create_analyzed_game(db, user, game_index=0, opening_acpl=20.0)
        _add_opening_moves(db, game, structure_key="chain")
        for index in range(1, MIN_GAMES_FOR_PROFILE):
            _create_analyzed_game(db, user, game_index=index, opening_acpl=20.0)

        here = _create_pattern(
            db,
            user,
            pattern_subtype="structure_slip_here",
            pattern_description="Recurring slip in this structure.",
            evidence={"structures": [{"structure_key": "chain", "occurrences": 4}]},
        )
        elsewhere = _create_pattern(
            db,
            user,
            pattern_subtype="structure_slip_elsewhere",
            pattern_description="Recurring slip somewhere else.",
            evidence={"structures": [{"structure_key": "other", "occurrences": 4}]},
        )

        profile = build_player_profile(db, user.id)
        entry = [
            item
            for item in profile.opening_repertoire["by_structure"]["structures"]
            if item["structure_key"] == "chain"
        ][0]

        assert entry["pattern_ids"] == [here.id]
        assert elsewhere.id not in entry["pattern_ids"]


class TestRepertoireStability:
    """Is there an opening repertoire at all? Measured, because it usually isn't.

    Real data forced this: one player's 143 games reached 136 distinct structures, so
    every structure group held a single game and the structure table could support no
    claim. "You have no repertoire yet" is the useful, honest answer — and it is the
    gap the ChessReps hand-off exists to close.
    """

    def test_scattered_openings_are_reported_as_no_repertoire(self, db):
        user = _create_user(db)
        # Five different lines across ten games: nothing repeats enough to prepare.
        lines = [
            "e2e4 e7e5 g1f3 b8c6",
            "d2d4 d7d5 c2c4 e7e6",
            "c2c4 e7e5 g1f3 b8c6",
            "g1f3 d7d5 d2d4 g8f6",
            "e2e4 c7c5 g1f3 d7d6",
        ]
        for index in range(MIN_GAMES_FOR_PROFILE):
            game, _ = _create_analyzed_game(db, user, game_index=index, opening_acpl=20.0)
            _set_first_moves(db, game, lines[index % len(lines)])

        profile = build_player_profile(db, user.id)
        repertoire = profile.opening_repertoire["by_structure"]["repertoire"]

        assert repertoire["distinct_lines"] == len(lines)
        assert repertoire["largest_group"] < REPERTOIRE_MIN_GAMES
        assert repertoire["verdict"] == "no_repertoire"
        assert repertoire["settled"] is False
        assert "repertoire" in repertoire["statement"].lower()

    def test_main_line_without_a_repertoire_says_both(self, db):
        """The real case: one line played often, overall repertoire still scattered.

        A single boolean had to lie about one of those facts, so the measurement
        reports a verdict plus a statement naming both.
        """
        user = _create_user(db)
        total = MIN_GAMES_FOR_PROFILE * 5
        for index in range(total):
            game, _ = _create_analyzed_game(db, user, game_index=index, opening_acpl=20.0)
            # Eight games share a line; the rest are all distinct (the trailing token
            # only has to differ — the measurement compares stored move strings).
            moves = "e2e4 e7e5 g1f3 b8c6" if index < 8 else f"d2d4 d7d5 c2c4 {index:04d}"
            _set_first_moves(db, game, moves)

        profile = build_player_profile(db, user.id)
        repertoire = profile.opening_repertoire["by_structure"]["repertoire"]

        assert repertoire["largest_group"] == 8
        assert repertoire["verdict"] == "main_line_only"
        assert repertoire["settled"] is False
        assert "main opening line" in repertoire["statement"]

    def test_repeated_line_is_reported_as_settled(self, db):
        user = _create_user(db)
        total = MIN_GAMES_FOR_PROFILE
        for index in range(total):
            game, _ = _create_analyzed_game(db, user, game_index=index, opening_acpl=20.0)
            _set_first_moves(db, game, "e2e4 e7e5 g1f3 b8c6")

        profile = build_player_profile(db, user.id)
        repertoire = profile.opening_repertoire["by_structure"]["repertoire"]

        assert repertoire["distinct_lines"] == 1
        assert repertoire["largest_group"] == total
        assert repertoire["settled"] is True
        assert repertoire["statement"]

    def test_stability_uses_the_configured_depth(self, db):
        user = _create_user(db)
        game, _ = _create_analyzed_game(db, user, game_index=0, opening_acpl=20.0)
        _set_first_moves(db, game, "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6")
        for index in range(1, MIN_GAMES_FOR_PROFILE):
            _create_analyzed_game(db, user, game_index=index, opening_acpl=20.0)

        profile = build_player_profile(db, user.id)
        repertoire = profile.opening_repertoire["by_structure"]["repertoire"]

        assert repertoire["depth"] == REPERTOIRE_DEPTH_PLIES
        # Four plies of that line, not six: the depth is the documented one.
        assert repertoire["distinct_lines"] == 1
