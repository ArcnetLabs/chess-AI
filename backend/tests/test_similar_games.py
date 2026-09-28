"""Tests for historical-game retrieval.

The properties that matter:

* it returns the player's *games*, not a flattened list of positions — the unit a
  coach recalls ("you have played this before, and here is how it went");
* a game needs more than one comparable position to count as "a game like this",
  because one shared position is a coincidence;
* the outcome summary counts only finished games, so an abandoned game cannot tilt
  it, and it expresses the result from the player's own side;
* when nothing is similar it says so rather than returning an arbitrary sample;
* the links are real: event types and pattern ids come from the stored rows for the
  matched moves, so a claim can be walked back.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.chess_event import ChessEvent
from app.models.game import Game, GameAnalysis
from app.models.game_move import GameMove
from app.models.pattern import PatternOccurrence, PlayerPattern
from app.services.retrieval.similar_decisions import MIN_SIMILARITY
from app.services.retrieval.similar_games import (
    MIN_MATCHING_PLIES,
    find_similar_games,
    format_similar_games_for_context,
    summarise_similar_games,
)

# Games are recalled by a shared pawn structure, not by feature vibe; the fixtures
# give every game this structure unless a test deliberately withholds it.
SHARED_STRUCTURE = "struct-shared"

# The situation under test: endgame, level material, simplified, own piece attacked.
TARGET_FEATURES = {
    "material_band": "level",
    "material_balance": 0,
    "simplified": True,
    "mover_hanging": ["d5"],
    "opponent_hanging": [],
    "mobility": 10,
}
OTHER_FEATURES = {
    "material_band": "ahead_decisive",
    "material_balance": 7,
    "simplified": False,
    "mover_hanging": [],
    "opponent_hanging": [],
    "mobility": 25,
}


@pytest.fixture
def user(db):
    from app.models.user import User

    row = User(
        supabase_user_id="similar-games-user",
        email="similargames@chessrun.local",
        chesscom_username="similar_games_player",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def add_game(
    db,
    user,
    *,
    index: int,
    winner: str = "white",
    user_colour: str = "white",
    days_ago: int = 1,
    opening_name: str = "Rook endgame",
) -> Game:
    game = Game(
        user_id=user.id,
        chesscom_game_id=f"similar-game-{index}",
        white_username="similar_games_player" if user_colour == "white" else "opponent",
        black_username="opponent" if user_colour == "white" else "similar_games_player",
        winner=winner,
        end_time=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(game)
    db.flush()
    db.add(
        GameAnalysis(
            game_id=game.id,
            user_color=user_colour,
            user_acpl=30.0,
            opponent_acpl=35.0,
            accuracy_percentage=80.0,
            opening_name=opening_name,
        )
    )
    db.commit()
    db.refresh(game)
    return game


def add_move(
    db,
    user,
    game: Game,
    *,
    ply: int,
    features: dict,
    structure_key: str = "struct-shared",
    colour: str | None = None,
    phases: str = "endgame",
    cp_loss: float = 20.0,
    event_type: str | None = None,
    pattern_id: int | None = None,
) -> GameMove:
    # Default to the side the player actually had in this game, so a fixture cannot
    # silently record the player as the wrong colour (which broke a result test).
    if colour is None:
        colour = "white" if game.white_username == user.chesscom_username else "black"
    move = GameMove(
        user_id=user.id,
        game_id=game.id,
        ply=ply,
        move_number=(ply + 1) // 2,
        color=colour,
        is_user_move=True,
        fen_before="8/8/8/8/8/8/8/8 w - - 0 1",
        fen_after="8/8/8/8/8/8/8/8 w - - 0 1",
        position_key=f"pos-{game.id}-{ply}",
        structure_key=structure_key,
        move_uci="e2e4",
        best_move_uci="e2e4",
        eval_before_cp=50.0,
        eval_after_cp=50.0 - cp_loss,
        cp_loss=cp_loss,
        classification="blunder" if event_type else "good",
        phase=phases,
        features=features,
    )
    db.add(move)
    db.flush()
    if event_type:
        db.add(
            ChessEvent(
                user_id=user.id,
                game_id=game.id,
                move_id=move.id,
                event_type=event_type,
                concept="endgame_technique",
                severity="high",
                phase=phases,
                move_number=move.move_number,
                position_key=move.position_key,
                fen_before=move.fen_before,
                cp_loss=cp_loss,
                detector_id="test",
                detector_version=1,
            )
        )
    if pattern_id:
        db.add(
            PatternOccurrence(
                pattern_id=pattern_id,
                user_id=user.id,
                move_id=move.id,
                game_id=game.id,
                move_number=move.move_number,
                game_phase=phases,
                fen_before=move.fen_before,
                fen_after=move.fen_after,
                user_move=move.move_uci,
                best_move=move.best_move_uci,
            )
        )
    db.commit()
    return move


class TestRetrieval:
    def test_returns_games_not_positions(self, db, user):
        game = add_game(db, user, index=1, winner="black", days_ago=2)
        # Three comparable positions inside one game -> one recalled game.
        for ply in (30, 33, 36):
            add_move(db, user, game, ply=ply, features=TARGET_FEATURES)

        results = find_similar_games(db, user.id, structure_key=SHARED_STRUCTURE, features=TARGET_FEATURES, phase="endgame")

        assert len(results) == 1
        assert results[0].game_id == game.id
        assert results[0].matching_plies == 3

    def test_a_single_shared_position_is_not_a_game_like_this(self, db, user):
        game = add_game(db, user, index=2)
        add_move(db, user, game, ply=30, features=TARGET_FEATURES)
        for ply in (32, 34):
            add_move(
                db, user, game, ply=ply, features=OTHER_FEATURES, structure_key="struct-other"
            )

        assert (
            find_similar_games(
                db, user.id, structure_key=SHARED_STRUCTURE, features=TARGET_FEATURES, phase="endgame"
            )
            == []
        )

    def test_an_unrelated_game_is_not_returned(self, db, user):
        """Same features, different structure: a different kind of game entirely."""
        game = add_game(db, user, index=3)
        for ply in (30, 33, 36):
            add_move(
                db, user, game, ply=ply, features=OTHER_FEATURES, structure_key="struct-other"
            )

        assert (
            find_similar_games(
                db, user.id, structure_key=SHARED_STRUCTURE, features=TARGET_FEATURES, phase="endgame"
            )
            == []
        )

    def test_a_single_exact_position_recall_is_enough(self, db, user):
        """One identical position in another game is decisive evidence by itself."""
        query_game = add_game(db, user, index=40, days_ago=3)
        other = add_game(db, user, index=41, days_ago=2)
        move = add_move(db, user, query_game, ply=30, features=TARGET_FEATURES)
        # The same position, reached in a different game, past the opening.
        twin = add_move(
            db,
            user,
            other,
            ply=42,
            features=TARGET_FEATURES,
            phases="middlegame",
        )
        twin.position_key = move.position_key
        db.commit()

        results = find_similar_games(
            db,
            user.id,
            position_key=move.position_key,
            exclude_game_id=query_game.id,
            min_matching_plies=MIN_MATCHING_PLIES,
        )

        assert [item.game_id for item in results] == [other.id]
        assert results[0].kind == "exact_position"

    def test_an_identical_opening_position_is_not_recall(self, db, user):
        """Every White game shares the start position; that is book, not experience."""
        query_game = add_game(db, user, index=42, days_ago=3)
        other = add_game(db, user, index=43, days_ago=2)
        first = add_move(db, user, query_game, ply=1, features=TARGET_FEATURES, phases="opening")
        twin = add_move(db, user, other, ply=1, features=TARGET_FEATURES, phases="opening")
        twin.position_key = first.position_key
        db.commit()

        results = find_similar_games(
            db,
            user.id,
            position_key=first.position_key,
            exclude_game_id=query_game.id,
        )

        assert results == []

    def test_feature_only_matching_is_refused_by_default(self, db, user):
        """The measurement behind the design: feature matching alone returns everything.

        On real data, every threshold up to and including a perfect six-of-six match
        returned 5 of 5 games, because that feature combination is the modal state of
        a chess game. So a caller must supply a structure or position anchor.
        """
        game = add_game(db, user, index=30)
        for ply in (30, 33):
            add_move(db, user, game, ply=ply, features=TARGET_FEATURES)

        # Identical features, no anchor: nothing is claimed.
        assert find_similar_games(db, user.id, features=TARGET_FEATURES, phase="endgame") == []

    def test_feature_only_matching_is_available_when_asked_for(self, db, user):
        game = add_game(db, user, index=31)
        for ply in (30, 33):
            add_move(db, user, game, ply=ply, features=TARGET_FEATURES)

        results = find_similar_games(
            db,
            user.id,
            features=TARGET_FEATURES,
            phase="endgame",
            allow_feature_only=True,
        )

        assert [item.game_id for item in results] == [game.id]

    def test_asking_with_nothing_is_not_an_error(self, db, user):
        game = add_game(db, user, index=4)
        add_move(db, user, game, ply=30, features=TARGET_FEATURES)
        assert find_similar_games(db, user.id) == []

    def test_the_game_being_discussed_is_never_its_own_history(self, db, user):
        game = add_game(db, user, index=5)
        for ply in (30, 33):
            add_move(db, user, game, ply=ply, features=TARGET_FEATURES)

        assert (
            find_similar_games(
                db,
                user.id,
                features=TARGET_FEATURES,
                phase="endgame",
                exclude_game_id=game.id,
            )
            == []
        )

    def test_result_is_from_the_players_own_side(self, db, user):
        won = add_game(db, user, index=6, winner="black", user_colour="black", days_ago=1)
        lost = add_game(db, user, index=7, winner="black", user_colour="white", days_ago=2)
        for game in (won, lost):
            for ply in (30, 33):
                add_move(db, user, game, ply=ply, features=TARGET_FEATURES)

        results = {item.game_id: item.result for item in find_similar_games(db, user.id, structure_key=SHARED_STRUCTURE, features=TARGET_FEATURES, phase="endgame")}

        assert results[won.id] == "win"
        assert results[lost.id] == "loss"

    def test_recency_breaks_ties(self, db, user):
        older = add_game(db, user, index=8, days_ago=30)
        newer = add_game(db, user, index=9, days_ago=1)
        for game in (older, newer):
            for ply in (30, 33):
                add_move(db, user, game, ply=ply, features=TARGET_FEATURES)

        results = find_similar_games(db, user.id, structure_key=SHARED_STRUCTURE, features=TARGET_FEATURES, phase="endgame")

        assert results[0].game_id == newer.id


class TestLinks:
    def test_event_types_and_patterns_come_from_the_matched_moves(self, db, user):
        game = add_game(db, user, index=10)
        pattern = PlayerPattern(
            user_id=user.id,
            pattern_type="decision_pattern",
            pattern_subtype="endgame_technique_failure__endgame|level|simplified|triggered",
            context_signature="endgame|level|simplified|triggered",
            severity="high",
            confidence_score=0.9,
            occurrence_count=5,
            affected_games_count=4,
            affected_games_ratio=0.5,
            pattern_description="Recurring pattern: an endgame technique error.",
        )
        db.add(pattern)
        db.commit()
        db.refresh(pattern)

        add_move(
            db,
            user,
            game,
            ply=30,
            features=TARGET_FEATURES,
            event_type="endgame_technique_failure",
            pattern_id=pattern.id,
        )
        add_move(db, user, game, ply=33, features=TARGET_FEATURES, event_type="tactical_miss")

        result = find_similar_games(db, user.id, structure_key=SHARED_STRUCTURE, features=TARGET_FEATURES, phase="endgame")[0]

        assert set(result.matched_event_types) == {"endgame_technique_failure", "tactical_miss"}
        assert result.pattern_ids == (pattern.id,)

    def test_a_pattern_from_another_game_is_not_attached(self, db, user):
        other = add_game(db, user, index=11)
        target = add_game(db, user, index=12, days_ago=2)
        pattern = PlayerPattern(
            user_id=user.id,
            pattern_type="decision_pattern",
            pattern_subtype="other__endgame|level|simplified|triggered",
            context_signature="endgame|level|simplified|triggered",
            severity="high",
            confidence_score=0.9,
            occurrence_count=5,
            affected_games_count=4,
            affected_games_ratio=0.5,
            pattern_description="Recurring pattern elsewhere.",
        )
        db.add(pattern)
        db.commit()
        db.refresh(pattern)
        add_move(
            db,
            user,
            other,
            ply=30,
            features=TARGET_FEATURES,
            event_type="tactical_miss",
            pattern_id=pattern.id,
        )
        for ply in (30, 33):
            add_move(db, user, target, ply=ply, features=TARGET_FEATURES)

        results = find_similar_games(db, user.id, structure_key=SHARED_STRUCTURE, features=TARGET_FEATURES, phase="endgame")
        target_result = [item for item in results if item.game_id == target.id][0]

        assert target_result.pattern_ids == ()


class TestSummary:
    def test_counts_only_finished_games(self, db, user):
        finished = add_game(db, user, index=13, winner="white")
        unfinished = add_game(db, user, index=14, winner="")  # no result recorded
        for game in (finished, unfinished):
            for ply in (30, 33):
                add_move(db, user, game, ply=ply, features=TARGET_FEATURES)

        games = find_similar_games(db, user.id, structure_key=SHARED_STRUCTURE, features=TARGET_FEATURES, phase="endgame")
        summary = summarise_similar_games(games)

        assert summary["games"] == 2
        assert summary["decided"] == 1
        assert summary["score_rate"] == 1.0

    def test_score_rate_is_from_the_players_side(self, db, user):
        win = add_game(db, user, index=15, winner="white", days_ago=1)
        draw = add_game(db, user, index=16, winner="draw", days_ago=2)
        loss = add_game(db, user, index=17, winner="black", days_ago=3)
        for game in (win, draw, loss):
            for ply in (30, 33):
                add_move(db, user, game, ply=ply, features=TARGET_FEATURES)

        summary = summarise_similar_games(
            find_similar_games(db, user.id, structure_key=SHARED_STRUCTURE, features=TARGET_FEATURES, phase="endgame")
        )

        assert summary["decided"] == 3
        assert summary["results"] == {"win": 1, "draw": 1, "loss": 1}
        assert summary["score_rate"] == 0.5

    def test_counts_games_where_the_same_thing_went_wrong(self, db, user):
        for index in (18, 19):
            game = add_game(db, user, index=index)
            for ply in (30, 33):
                add_move(
                    db,
                    user,
                    game,
                    ply=ply,
                    features=TARGET_FEATURES,
                    event_type="endgame_technique_failure",
                )

        summary = summarise_similar_games(
            find_similar_games(db, user.id, structure_key=SHARED_STRUCTURE, features=TARGET_FEATURES, phase="endgame")
        )

        assert summary["games_with_the_same_problem"] == 2
        assert summary["common_event_types"] == ["endgame_technique_failure"]


class TestContextBlock:
    def test_block_states_the_record_and_names_the_games(self, db, user):
        game = add_game(db, user, index=20, winner="black", user_colour="white")
        for ply in (30, 33):
            add_move(
                db,
                user,
                game,
                ply=ply,
                features=TARGET_FEATURES,
                event_type="endgame_technique_failure",
            )

        block = format_similar_games_for_context(
            find_similar_games(db, user.id, structure_key=SHARED_STRUCTURE, features=TARGET_FEATURES, phase="endgame")
        )

        assert "Your games in this kind of position" in block
        assert "scored 0%" in block
        assert "the same thing went wrong" in block
        assert f"Game {game.id}" in block

    def test_no_games_produces_no_block(self):
        assert format_similar_games_for_context([]) == ""
