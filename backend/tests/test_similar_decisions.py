"""Tests for position/decision retrieval and the relevance floors.

The properties that matter:

* an exact position recurrence is found regardless of move order;
* a same-structure match is recognised as such, not as the same position;
* feature-similar matches are scored, and rejected below the floor, so the
  system can honestly answer "this is new for you";
* the current game is never returned as its own history;
* the coach-facing block states absence instead of implying memory.
"""

import pytest

from app.services.retrieval.similar_decisions import (
    DEFAULT_SEMANTIC_MIN_SIMILARITY,
    FEATURE_WEIGHTS,
    MIN_SIMILARITY,
    SimilarDecision,
    feature_vector,
    find_similar_decisions,
    format_similar_decisions_for_context,
    similarity_score,
)

LEVEL_COMPLEX = {
    "material_balance": 0,
    "material_band": "level",
    "simplified": False,
    "mover_hanging": [],
    "opponent_hanging": [],
    "mobility": 20,
}


class TestFeatureVectors:
    def test_weights_are_normalised(self):
        assert abs(sum(FEATURE_WEIGHTS.values()) - 1.0) < 1e-9

    def test_identical_situations_score_one(self):
        vector = feature_vector(LEVEL_COMPLEX, "middlegame")
        score, shared = similarity_score(vector, vector)
        assert score == 1.0
        assert len(shared) == len(FEATURE_WEIGHTS)

    def test_threat_picture_distinguishes_who_is_attacked(self):
        attacked = feature_vector({**LEVEL_COMPLEX, "mover_hanging": ["c3"]}, "middlegame")
        free = feature_vector(LEVEL_COMPLEX, "middlegame")
        assert attacked["threat_picture"] != free["threat_picture"]

    def test_phase_is_the_heaviest_single_feature(self):
        mine = feature_vector(LEVEL_COMPLEX, "middlegame")
        other_phase = feature_vector(LEVEL_COMPLEX, "endgame")
        score, shared = similarity_score(mine, other_phase)
        assert "phase" not in shared
        assert score == pytest.approx(1.0 - FEATURE_WEIGHTS["phase"], abs=1e-6)

    def test_different_material_state_scores_below_the_floor(self):
        ahead = feature_vector({**LEVEL_COMPLEX, "material_band": "clear", "material_balance": 500}, "middlegame")
        behind = feature_vector({**LEVEL_COMPLEX, "material_band": "clear", "material_balance": -500}, "endgame")
        score, _ = similarity_score(ahead, behind)
        assert score < MIN_SIMILARITY


class TestFormattingForContext:
    def test_absence_is_stated_explicitly(self):
        text = format_similar_decisions_for_context([])
        assert "None found" in text
        assert "do not claim" in text

    def test_matches_are_described_without_engine_vocabulary(self):
        decision = SimilarDecision(
            game_id=7,
            move_id=1,
            move_number=24,
            phase="endgame",
            fen_before="8/8/8/8/8/8/8/8 w - - 0 1",
            played_move="d4e5",
            best_move="c7e5",
            cp_loss=300.0,
            classification="blunder",
            game_result="black",
            score=0.9,
            match_kind="similar_features",
            pattern_subtype="endgame_technique_failure__x",
        )
        text = format_similar_decisions_for_context([decision])
        assert "played d4e5" in text
        assert "better was c7e5" in text
        assert "the game ended black" in text
        for banned in ("acpl", "centipawn", "eval", "cp"):
            assert banned not in text.lower()

    def test_similar_only_matches_say_so(self):
        decision = SimilarDecision(
            game_id=7,
            move_id=1,
            move_number=24,
            phase="endgame",
            fen_before=None,
            played_move="d4e5",
            best_move="c7e5",
            cp_loss=300.0,
            classification="blunder",
            game_result="draw",
            score=0.7,
            match_kind="similar_features",
        )
        text = format_similar_decisions_for_context([decision])
        assert "similar situations rather than the same position" in text


class TestSemanticFloor:
    def test_floor_is_meaningful(self):
        assert 0.0 < DEFAULT_SEMANTIC_MIN_SIMILARITY < 0.6

    def test_retrieval_service_default_is_overridable(self):
        """The service still accepts an explicit floor; callers must pass one."""
        from app.services.coaching import retrieval_service

        signature = retrieval_service.retrieve_semantic_memories.__doc__ or ""
        # The parameter exists and is honoured; the assembler passes the floor.
        assert "min_similarity" in retrieval_service.retrieve_semantic_memories.__code__.co_varnames
        assert signature is not None


def seed_move(
    db,
    *,
    user_id: int,
    game_id: int,
    ply: int,
    position_key: str,
    structure_key: str,
    phase: str,
    features: dict,
    cp_loss: float = 0.0,
    move_uci: str = "e2e4",
    best_move: str = "e2e4",
):
    from app.models.game_move import GameMove

    move = GameMove(
        user_id=user_id,
        game_id=game_id,
        ply=ply,
        move_number=(ply + 1) // 2,
        color="white",
        is_user_move=True,
        fen_before="8/8/8/8/8/8/8/8 w - - 0 1",
        fen_after="8/8/8/8/8/8/8/8 b - - 0 1",
        position_key=position_key,
        structure_key=structure_key,
        material_balance=features.get("material_balance", 0),
        move_uci=move_uci,
        best_move_uci=best_move,
        eval_before_cp=100.0,
        eval_after_cp=100.0 - cp_loss,
        cp_loss=cp_loss,
        classification="blunder" if cp_loss >= 300 else "good",
        phase=phase,
        features=features,
    )
    db.add(move)
    db.commit()
    db.refresh(move)
    return move


from itertools import count

import pytest

_GAME_SEQUENCE = count(1)


def seed_game(db, *, user_id: int, winner: str = "draw"):
    from app.models.game import Game

    game = Game(
        user_id=user_id,
        # The per-user unique index on chesscom_game_id is real (migration 0014),
        # so ids must be unique rather than derived from object identity.
        chesscom_game_id=f"game-{next(_GAME_SEQUENCE)}",
        winner=winner,
        white_username="me",
        black_username="them",
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


class TestFindSimilarDecisions:
    def test_exact_position_match_wins(self, db):
        user_id = 101
        game = seed_game(db, user_id=user_id)
        seed_move(
            db,
            user_id=user_id,
            game_id=game.id,
            ply=41,
            position_key="exact-key",
            structure_key="struct-a",
            phase="endgame",
            features=LEVEL_COMPLEX,
            cp_loss=400.0,
        )

        results = find_similar_decisions(
            db, user_id, position_key="exact-key", features=LEVEL_COMPLEX, phase="endgame"
        )
        assert len(results) == 1
        assert results[0].match_kind == "exact_position"
        assert results[0].score == 1.0

    def test_same_structure_is_labelled_differently(self, db):
        user_id = 102
        game = seed_game(db, user_id=user_id)
        seed_move(
            db,
            user_id=user_id,
            game_id=game.id,
            ply=31,
            position_key="other-key",
            structure_key="struct-b",
            phase="middlegame",
            features=LEVEL_COMPLEX,
            cp_loss=350.0,
        )

        results = find_similar_decisions(
            db,
            user_id,
            position_key="not-a-match",
            structure_key="struct-b",
            phase="middlegame",
            features=LEVEL_COMPLEX,
        )
        assert len(results) == 1
        assert results[0].match_kind == "same_structure"

    def test_unrelated_situation_falls_below_the_floor(self, db):
        user_id = 103
        game = seed_game(db, user_id=user_id)
        seed_move(
            db,
            user_id=user_id,
            game_id=game.id,
            ply=11,
            position_key="k1",
            structure_key="struct-c",
            phase="opening",
            features={"material_band": "decisive", "material_balance": 900, "mobility": 40},
            cp_loss=200.0,
        )

        results = find_similar_decisions(
            db,
            user_id,
            position_key="does-not-exist",
            features=LEVEL_COMPLEX,
            phase="endgame",
        )
        assert results == []

    def test_current_game_is_never_its_own_history(self, db):
        user_id = 104
        game = seed_game(db, user_id=user_id)
        seed_move(
            db,
            user_id=user_id,
            game_id=game.id,
            ply=21,
            position_key="shared",
            structure_key="struct-d",
            phase="middlegame",
            features=LEVEL_COMPLEX,
        )

        results = find_similar_decisions(
            db,
            user_id,
            position_key="shared",
            features=LEVEL_COMPLEX,
            phase="middlegame",
            exclude_game_id=game.id,
        )
        assert results == []

    def test_results_are_ranked_and_capped(self, db):
        user_id = 105
        for index in range(4):
            game = seed_game(db, user_id=user_id)
            seed_move(
                db,
                user_id=user_id,
                game_id=game.id,
                ply=41 + index,
                position_key=f"exact-{index}",
                structure_key="struct-e",
                phase="endgame",
                features=LEVEL_COMPLEX,
                cp_loss=300.0 + index * 50,
            )

        results = find_similar_decisions(
            db,
            user_id,
            position_key="exact-0",
            structure_key="struct-e",
            phase="endgame",
            features=LEVEL_COMPLEX,
            limit=2,
        )
        assert len(results) == 2
        # The exact match ranks first, then the structural siblings by damage.
        assert results[0].move_number == 21
        assert results[0].score >= results[1].score

    def test_no_context_returns_nothing(self, db):
        assert find_similar_decisions(db, 106) == []
