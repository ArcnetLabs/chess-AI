"""Historical-game retrieval: the player's own games that resemble this one.

Where ``similar_decisions`` answers "have I seen this position before?", this answers
"have I *played* this kind of game before, and how did it go?" — a game-level
question, which is the one a coach asks when a player wants to know whether a
problem is a habit or a one-off.

It is built on the same machinery rather than a parallel implementation: the
candidate scan and the categorical feature vector come from ``similar_decisions``, so
a position is "similar" by one definition in the whole system.

**Game-level retrieval is anchored on structure or exact position, not on feature
similarity.** That is a measured decision, not a preference. Running the feature-only
version against a real player (143 games, 4,302 decisions) at every threshold:

| Threshold | Middlegame games returned | Flagged "same problem" |
|---|---|---|
| 0.62 (the decision-level floor) | 5 | 5 |
| 0.80 | 5 | 5 |
| 1.00 — every feature matching | 5 | 5 |

A perfect six-of-six feature match still describes most middlegame positions, because
that combination (level material, complex, no threats, normal mobility, self-initiated)
*is* the modal state of a chess game. Feature similarity therefore cannot answer "have
I played a game like this?" — it returns "you have played chess". The endgame case
became selective only at 0.8+, and exact pawn structure is what genuinely repeats: 84
structures appear in two or more of that player's games, one of them in 71.

So a game is recalled when it shares the **structure** or the **exact position**;
features rank and explain the matches rather than admitting them. ``allow_feature_only``
exists for callers that knowingly want the looser behaviour, and defaults to off.

Everything is measured from stored rows: no engine call, no model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from app.models.chess_event import ChessEvent
from app.models.game import Game, GameAnalysis
from app.models.game_move import GameMove
from app.models.pattern import PatternOccurrence

from .similar_decisions import (
    CANDIDATE_SCAN_LIMIT,
    MIN_SIMILARITY,
    feature_vector,
    similarity_score,
)

# A game needs at least this many similar decisions before it is "a game like this".
# One shared position is a coincidence; a game that keeps arriving in the situation
# is the thing worth recalling.
MIN_MATCHING_PLIES = 2
# How many games to return by default.
MAX_SIMILAR_GAMES = 5
# Score floor for a structural match: below an exact position (1.0), above the
# feature floor, because sharing a pawn skeleton is stronger evidence than sharing a
# phase and a material band but weaker than the same position.
STRUCTURE_MATCH_SCORE = 0.75

KIND_SAME_STRUCTURE = "same_structure"
KIND_SIMILAR_FEATURES = "similar_features"


@dataclass
class SimilarGame:
    """One of the player's games that resembled the situation, with its outcome."""

    game_id: int
    played_at: Optional[str] = None
    opponent: Optional[str] = None
    player_colour: Optional[str] = None
    result: Optional[str] = None  # win | draw | loss, from the player's side
    opening_name: Optional[str] = None
    matching_plies: int = 0
    best_score: float = 0.0
    kind: str = KIND_SIMILAR_FEATURES
    shared_features: Tuple[str, ...] = ()
    matched_event_types: Tuple[str, ...] = ()
    pattern_ids: Tuple[int, ...] = ()
    example_ply: Optional[int] = None

    def describe(self) -> str:
        """A factual sentence, for context blocks and coach grounding."""
        when = f" on {self.played_at}" if self.played_at else ""
        opponent = f" against {self.opponent}" if self.opponent else ""
        opening = f" ({self.opening_name})" if self.opening_name else ""
        outcome = f", {self.result}" if self.result else ""
        events = (
            f"; the same problem appeared: {', '.join(self.matched_event_types)}"
            if self.matched_event_types
            else ""
        )
        return (
            f"Game {self.game_id}{when}{opponent}{opening}{outcome} — "
            f"{self.matching_plies} comparable positions{events}"
        )


def _scan_candidates(
    db: Session, user_id: int, exclude_game_id: Optional[int]
) -> List[GameMove]:
    """Recent user moves, newest games first.

    Ordered by game end time rather than row id: ordering by id silently sampled
    whichever games happened to be analysed last, which is a retrieval bug that
    looks like a relevance problem.
    """
    query = db.query(GameMove).filter(
        GameMove.user_id == user_id, GameMove.is_user_move.is_(True)
    )
    if exclude_game_id is not None:
        query = query.filter(GameMove.game_id != exclude_game_id)
    return (
        query.join(Game, Game.id == GameMove.game_id)
        .order_by(Game.end_time.desc().nullslast(), GameMove.ply.desc())
        .limit(CANDIDATE_SCAN_LIMIT)
        .all()
    )


def _score_move(
    move: GameMove,
    target: Dict[str, str],
    *,
    position_key: Optional[str],
    structure_key: Optional[str],
    phase: Optional[str],
    min_similarity: float,
    anchor_required: bool,
) -> Optional[Tuple[float, str, List[str]]]:
    """Score one stored move against the target, or ``None`` if it is not similar.

    Without an anchor the feature score is only used when the caller explicitly asked
    for feature-only matching.
    """
    if position_key and move.position_key == position_key:
        return 1.0, "exact_position", ["position_key"]

    score, shared = similarity_score(
        target, feature_vector(move.features or {}, move.phase)
    )
    if structure_key and move.structure_key == structure_key:
        return max(score, STRUCTURE_MATCH_SCORE), KIND_SAME_STRUCTURE, shared
    if anchor_required:
        return None
    if score < min_similarity:
        return None
    return score, KIND_SIMILAR_FEATURES, shared


def _player_result(game: Game, colour: Optional[str]) -> Optional[str]:
    winner = (game.winner or "").lower()
    if winner == "draw":
        return "draw"
    if winner in ("white", "black"):
        if not colour:
            return None
        return "win" if winner == colour else "loss"
    return None


def _colour_of(moves: Sequence[GameMove]) -> Optional[str]:
    for move in moves:
        if move.is_user_move and move.color:
            return str(move.color).lower()
    return None


def _opponent_of(game: Game, colour: Optional[str]) -> Optional[str]:
    if colour == "white":
        return game.black_username
    if colour == "black":
        return game.white_username
    return None


def find_similar_games(
    db: Session,
    user_id: int,
    *,
    fen: Optional[str] = None,
    position_key: Optional[str] = None,
    structure_key: Optional[str] = None,
    phase: Optional[str] = None,
    features: Optional[Dict] = None,
    exclude_game_id: Optional[int] = None,
    limit: int = MAX_SIMILAR_GAMES,
    min_similarity: float = MIN_SIMILARITY,
    min_matching_plies: int = MIN_MATCHING_PLIES,
    allow_feature_only: bool = False,
) -> List[SimilarGame]:
    """The player's past games that most resemble the given situation.

    Needs a **structure or exact-position anchor**; features alone do not admit a
    game (see the module docstring for the measurement behind that).

    Returns ``[]`` rather than an arbitrary sample when nothing qualifies: "you have
    not played this before" is a real answer, and the coach needs to be able to say
    it.
    """
    if fen:
        import chess

        from app.services.analysis.position_features import (
            extract_features,
            position_key as position_key_of,
            structure_key as structure_key_of,
        )

        board = chess.Board(fen)
        position_key = position_key or position_key_of(board)
        structure_key = structure_key or structure_key_of(board)
        features = features or extract_features(board)

    if not (position_key or structure_key) and not allow_feature_only:
        # Silent by design, and logged: a caller asking for games "like this" with
        # nothing distinctive to match on would otherwise get the whole library back
        # and mistake volume for relevance.
        logger.debug(
            f"similar-games user={user_id}: no structure or position anchor; "
            f"returning nothing rather than every game"
        )
        return []

    if not any([position_key, structure_key, features]):
        return []

    candidates = _scan_candidates(db, user_id, exclude_game_id)
    if not candidates:
        return []
    if len(candidates) == CANDIDATE_SCAN_LIMIT:
        logger.debug(
            f"similar-games user={user_id}: scan capped at {CANDIDATE_SCAN_LIMIT} moves"
        )

    target = feature_vector(features, phase)

    # Aggregate similar decisions into facts about their game.
    per_game: Dict[int, Dict] = {}
    for move in candidates:
        scored = _score_move(
            move,
            target,
            position_key=position_key,
            structure_key=structure_key,
            phase=phase,
            min_similarity=min_similarity,
            anchor_required=not allow_feature_only,
        )
        if scored is None:
            continue
        score, kind, shared = scored
        bucket = per_game.setdefault(
            move.game_id,
            {
                "moves": [],
                "best_score": 0.0,
                "kind": kind,
                "shared": [],
                "example_ply": None,
                "strong_single": False,
            },
        )
        bucket["moves"].append(move)
        if kind == "exact_position" and (move.phase or "") != "opening":
            # One *exact* recurrence outside the opening is decisive on its own: the
            # player has stood in this precise position in another game. Inside the
            # opening it is not — identical book positions are shared knowledge, not
            # experience, and every White game would "recall" every other.
            bucket["strong_single"] = True
        if score > bucket["best_score"]:
            bucket["best_score"] = score
            bucket["kind"] = kind
            bucket["shared"] = shared
            bucket["example_ply"] = move.ply

    qualifying = {
        game_id: bucket
        for game_id, bucket in per_game.items()
        if len(bucket["moves"]) >= min_matching_plies or bucket["strong_single"]
    }
    if not qualifying:
        return []

    games = {
        game.id: game
        for game in db.query(Game).filter(Game.id.in_(qualifying)).all()
    }
    analyses = {
        analysis.game_id: analysis
        for analysis in db.query(GameAnalysis)
        .filter(GameAnalysis.game_id.in_(qualifying))
        .all()
    }

    matched_move_ids = [m.id for bucket in qualifying.values() for m in bucket["moves"]]
    events_by_move = _events_by_move(db, matched_move_ids)
    patterns_by_move = _patterns_by_move(db, matched_move_ids)

    results: List[SimilarGame] = []
    for game_id, bucket in qualifying.items():
        game = games.get(game_id)
        if game is None:
            continue
        moves = bucket["moves"]
        colour = _colour_of(moves)
        analyses_row = analyses.get(game_id)
        event_types = sorted(
            {event_type for move in moves for event_type in events_by_move.get(move.id, ())}
        )
        pattern_ids = sorted(
            {pid for move in moves for pid in patterns_by_move.get(move.id, ())}
        )
        results.append(
            SimilarGame(
                game_id=game_id,
                played_at=game.end_time.date().isoformat() if game.end_time else None,
                opponent=_opponent_of(game, colour),
                player_colour=colour,
                result=_player_result(game, colour),
                opening_name=getattr(analyses_row, "opening_name", None),
                matching_plies=len(moves),
                best_score=bucket["best_score"],
                kind=bucket["kind"],
                shared_features=tuple(bucket["shared"]),
                matched_event_types=tuple(event_types),
                pattern_ids=tuple(pattern_ids),
                example_ply=bucket["example_ply"],
            )
        )

    results.sort(
        key=lambda item: (item.best_score, item.matching_plies, item.played_at or ""),
        reverse=True,
    )
    return results[:limit]


def _events_by_move(db: Session, move_ids: Sequence[int]) -> Dict[int, List[str]]:
    if not move_ids:
        return {}
    mapping: Dict[int, List[str]] = {}
    rows = (
        db.query(ChessEvent.move_id, ChessEvent.event_type)
        .filter(ChessEvent.move_id.in_(move_ids))
        .all()
    )
    for move_id, event_type in rows:
        mapping.setdefault(move_id, []).append(event_type)
    return mapping


def _patterns_by_move(db: Session, move_ids: Sequence[int]) -> Dict[int, List[int]]:
    """Pattern ids this move is already stored evidence for."""
    if not move_ids:
        return {}
    mapping: Dict[int, List[int]] = {}
    rows = (
        db.query(PatternOccurrence.move_id, PatternOccurrence.pattern_id)
        .filter(PatternOccurrence.move_id.in_(move_ids))
        .all()
    )
    for move_id, pattern_id in rows:
        mapping.setdefault(move_id, []).append(pattern_id)
    return mapping


def summarise_similar_games(games: Sequence[SimilarGame]) -> Dict:
    """Outcome summary across the retrieved games.

    This is the number a coach actually uses: "in the 12 games you reached this kind
    of position, you scored 4/12". Counted only over games with a known result, so an
    unfinished game cannot tilt it.
    """
    decided = [game for game in games if game.result in ("win", "draw", "loss")]
    if not decided:
        return {"games": len(games), "decided": 0, "score_rate": None, "results": {}}

    points = {"win": 1.0, "draw": 0.5, "loss": 0.0}
    total = sum(points[game.result] for game in decided)
    counts: Dict[str, int] = {}
    for game in decided:
        counts[game.result] = counts.get(game.result, 0) + 1

    with_problem = [game for game in decided if game.matched_event_types]
    return {
        "games": len(games),
        "decided": len(decided),
        "score_rate": round(total / len(decided), 3),
        "results": counts,
        "games_with_the_same_problem": len(with_problem),
        "common_event_types": _common_event_types(decided),
    }


def _common_event_types(games: Sequence[SimilarGame], limit: int = 3) -> List[str]:
    counts: Dict[str, int] = {}
    for game in games:
        for event_type in set(game.matched_event_types):
            counts[event_type] = counts.get(event_type, 0) + 1
    return [name for name, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:limit]]


def format_similar_games_for_context(games: Sequence[SimilarGame]) -> str:
    """A context block the coach can cite, or an explicit statement of absence."""
    if not games:
        return ""

    summary = summarise_similar_games(games)
    lines = ["## Your games in this kind of position"]
    if summary["score_rate"] is not None:
        results = summary["results"]
        lines.append(
            f"You have reached it in {summary['decided']} finished games and scored "
            f"{round(summary['score_rate'] * 100)}% "
            f"({results.get('win', 0)}W/{results.get('draw', 0)}D/{results.get('loss', 0)}L)."
        )
    if summary.get("games_with_the_same_problem"):
        lines.append(
            f"In {summary['games_with_the_same_problem']} of them the same thing went wrong."
        )
    for game in games:
        lines.append(f"- {game.describe()}")
    return "\n".join(lines)
