"""Retrieve the player's genuinely similar past decisions.

The question the coach has to be able to answer is *"have I seen this player in
this situation before, what did they do, and how did it end?"* — grounded in
stored rows, not in the model's imagination. Text retrieval answers "what have we
discussed"; this answers "what have you done in this position".

Three-stage match, cheapest first (see
``docs/architecture/PLAYER_INTELLIGENCE_ARCHITECTURE.md`` §6):

1. **Same position** — identical normalised ``position_key``. Exact recurrence of
   the position itself, regardless of move order.
2. **Same structure and phase** — identical pawn skeleton in the same phase, i.e.
   the same *kind* of position reached by different move orders.
3. **Similar features** — a weighted distance over the stored move features
   (material state, complexity, threats, mobility, opponent trigger), scored and
   thresholded.

A relevance floor applies to stage 3: below it, the honest answer is "no similar
history", and a retrieval path that cannot say that is useless as evidence. That
floor is the fix for the gap the audit found in the text path, where
``min_similarity`` was never set and therefore never filtered anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from app.models.game import Game
from app.models.game_move import GameMove
from app.models.pattern import PatternOccurrence

# Feature-similar matches must clear this to be returned. Tuned so a match must
# share the situation's essentials — phase, material state, complexity and threat
# picture — rather than merely being a legal move in some middlegame.
MIN_SIMILARITY = 0.62

# How many of the player's most recent moves one retrieval scans. Bounded so the
# path stays cheap: a full library is ~10k moves, and ranking 2k recent ones is
# already a few milliseconds without an index of its own.
CANDIDATE_SCAN_LIMIT = 2000

# How many matches one game may contribute. Repetition inside a single game is
# weaker evidence than the same decision recurring across games, which is the
# whole point of a longitudinal coach.
MAX_MATCHES_PER_GAME = 2

# Relevance floor for the *text* retrieval path (semantic memory). The audit found
# ``min_similarity`` defaulted to 0.0 and was never passed by any caller, so every
# stored memory passed the filter regardless of relevance — "recall" that could
# not distinguish a match from a non-match. Unrelated text embeddings land around
# 0.1-0.2 cosine similarity, so 0.3 keeps genuine topical matches and drops noise.
DEFAULT_SEMANTIC_MIN_SIMILARITY = 0.3

# How much each feature contributes to a stage-3 similarity score. Weights sum
# to 1.0 so the score is directly comparable to MIN_SIMILARITY.
FEATURE_WEIGHTS: Dict[str, float] = {
    "phase": 0.30,
    "material_state": 0.25,
    "complexity": 0.15,
    "threat_picture": 0.15,
    "mobility_band": 0.10,
    "trigger": 0.05,
}


@dataclass
class SimilarDecision:
    """A past decision the current situation resembles."""

    game_id: int
    move_id: int
    move_number: int
    phase: Optional[str]
    fen_before: Optional[str]
    played_move: Optional[str]
    best_move: Optional[str]
    cp_loss: float
    classification: Optional[str]
    game_result: Optional[str]
    score: float
    match_kind: str  # exact_position | same_structure | similar_features
    event_types: Tuple[str, ...] = ()
    pattern_subtype: Optional[str] = None
    context_description: Optional[str] = None
    shared_context: List[str] = field(default_factory=list)

    def outcome_text(self) -> str:
        """Plain-language outcome, with no engine vocabulary."""
        if self.game_result is None:
            return "that game is not finished"
        return f"the game ended {self.game_result}"


def _mobility_band(features: Dict) -> str:
    mobility = features.get("mobility")
    if not isinstance(mobility, (int, float)):
        return "unknown"
    if mobility <= 3:
        return "restricted"
    if mobility <= 12:
        return "normal"
    return "active"


def _threat_picture(features: Dict) -> str:
    own_hanging = bool(features.get("mover_hanging"))
    their_hanging = bool(features.get("opponent_hanging"))
    if own_hanging and their_hanging:
        return "both"
    if own_hanging:
        return "own_piece_attacked"
    if their_hanging:
        return "their_piece_available"
    return "quiet"


def _material_state(features: Dict) -> str:
    band = features.get("material_band") or "unknown"
    balance = features.get("material_balance")
    if band == "level" or not isinstance(balance, (int, float)):
        return band
    return f"{'ahead' if balance > 0 else 'behind'}_{band}"


def feature_vector(features: Optional[Dict], phase: Optional[str]) -> Dict[str, str]:
    """Categorical feature vector used for stage-3 similarity."""
    features = features or {}
    return {
        "phase": phase or "unknown",
        "material_state": _material_state(features),
        "complexity": "simplified" if features.get("simplified") else "complex",
        "threat_picture": _threat_picture(features),
        "mobility_band": _mobility_band(features),
        "trigger": "triggered" if features.get("mover_hanging") else "self_initiated",
    }


def similarity_score(left: Dict[str, str], right: Dict[str, str]) -> Tuple[float, List[str]]:
    """Weighted agreement between two feature vectors.

    Returns the score and the features that actually matched, so a caller can say
    *why* two positions are being called similar rather than asserting it.
    """
    score = 0.0
    shared: List[str] = []
    for name, weight in FEATURE_WEIGHTS.items():
        if left.get(name) and left.get(name) == right.get(name):
            score += weight
            shared.append(name)
    return round(score, 4), shared


def _pattern_for_move(db: Session, move_id: int) -> Optional[str]:
    """Subtype of a pattern this move is already evidence for, if any."""
    occurrence = (
        db.query(PatternOccurrence)
        .filter(PatternOccurrence.move_id == move_id)
        .first()
    )
    if occurrence is None or occurrence.pattern is None:
        return None
    return occurrence.pattern.pattern_subtype


def _legal_best_move(move: GameMove) -> Optional[str]:
    """The stored best move, but only if the player could actually have played it.

    Rows written before the analyzer fix store the *opponent's* best reply: the
    engine was queried after the move was pushed, so ``best_move`` belongs to the
    side to move in ``fen_after``. Measured on production, 2,982 of 3,000 stored best
    moves were legal in ``fen_after`` and **none** were legal in neither, which is
    what identified the cause.

    Rather than show a player advice they could not follow ("you played f2f4, better
    was b8c6" — a Black move offered to White), an unusable best move is dropped
    here, in one place, so every consumer is protected at once. Historical rows keep
    their stored value; it simply is not presented as an alternative.
    """
    if not move.best_move_uci or not move.fen_before:
        return None
    if move.best_move_uci == move.move_uci:
        return move.best_move_uci
    try:
        import chess

        board = chess.Board(move.fen_before)
        return (
            move.best_move_uci
            if chess.Move.from_uci(move.best_move_uci) in board.legal_moves
            else None
        )
    except Exception:
        return None


def _to_decision(
    move: GameMove,
    game: Optional[Game],
    *,
    score: float,
    match_kind: str,
    features: Dict,
    shared: Sequence[str],
    pattern_subtype: Optional[str],
) -> SimilarDecision:
    return SimilarDecision(
        game_id=move.game_id,
        move_id=move.id,
        move_number=move.move_number,
        phase=move.phase,
        fen_before=move.fen_before,
        played_move=move.move_uci,
        best_move=_legal_best_move(move),
        cp_loss=float(move.cp_loss or 0.0),
        classification=move.classification,
        game_result=game.winner if game else None,
        score=score,
        match_kind=match_kind,
        shared_context=list(shared),
        pattern_subtype=pattern_subtype,
        context_description=", ".join(shared) if shared else None,
    )


def find_similar_decisions(
    db: Session,
    user_id: int,
    *,
    fen: Optional[str] = None,
    position_key: Optional[str] = None,
    structure_key: Optional[str] = None,
    phase: Optional[str] = None,
    features: Optional[Dict] = None,
    exclude_game_id: Optional[int] = None,
    only_user_moves: bool = True,
    limit: int = 5,
    min_similarity: float = MIN_SIMILARITY,
) -> List[SimilarDecision]:
    """Find the player's past decisions that resemble the given situation.

    Any of ``position_key``/``fen``/``structure_key`` + ``features`` may be given;
    the more context supplied, the better the ranking. Passing nothing returns an
    empty list rather than an arbitrary sample.
    """
    if not any([position_key, fen, structure_key, features]):
        return []

    query = db.query(GameMove).filter(GameMove.user_id == user_id)
    if only_user_moves:
        query = query.filter(GameMove.is_user_move.is_(True))
    if exclude_game_id is not None:
        # Never "recall" the game currently being discussed as history.
        query = query.filter(GameMove.game_id != exclude_game_id)

    # Recency means the most recent *games*, not the most recently inserted rows:
    # ordering by move id silently sampled whichever games happened to be
    # analysed last. Structure is deliberately NOT a SQL filter — filtering on an
    # exact pawn skeleton returned zero candidates for a real endgame where
    # similar positions did exist; structure is a ranking signal, not a gate.
    candidates = (
        query.join(Game, Game.id == GameMove.game_id)
        .order_by(Game.end_time.desc().nullslast(), GameMove.ply.desc())
        .limit(CANDIDATE_SCAN_LIMIT)
        .all()
    )
    if len(candidates) == CANDIDATE_SCAN_LIMIT:
        logger.debug(
            f"similar-decisions user={user_id}: scan capped at {CANDIDATE_SCAN_LIMIT} moves"
        )
    if not candidates:
        return []

    target = feature_vector(features, phase)
    games = {
        game.id: game
        for game in db.query(Game)
        .filter(Game.id.in_({move.game_id for move in candidates}))
        .all()
    }

    scored: List[SimilarDecision] = []
    for move in candidates:
        move_features = move.features or {}
        score, shared = similarity_score(target, feature_vector(move_features, move.phase))

        if position_key and move.position_key == position_key:
            kind, score = "exact_position", 1.0
        elif structure_key and move.structure_key == structure_key and move.phase == phase:
            kind = "same_structure"
            score = max(score, 0.75)
        else:
            kind = "similar_features"
            if score < min_similarity:
                continue

        scored.append(
            _to_decision(
                move,
                games.get(move.game_id),
                score=score,
                match_kind=kind,
                features=move_features,
                shared=shared,
                pattern_subtype=_pattern_for_move(db, move.id),
            )
        )

    # Ranking: match kind first, then score, then how instructive the mistake was.
    # Kind must outrank score because an exact recurrence of the position is
    # stronger evidence than a high feature agreement — otherwise a
    # feature-identical sibling can tie with (and displace) the same position.
    match_rank = {"exact_position": 3, "same_structure": 2, "similar_features": 1}
    scored.sort(key=lambda item: (-match_rank[item.match_kind], -item.score, -item.cp_loss))

    # Spread the evidence across games. Live output clustered four of five matches
    # in a single game, and "you did this three times" is a much weaker coaching
    # claim than "you did this in three different games".
    results: List[SimilarDecision] = []
    per_game: Dict[int, int] = {}
    for decision in scored:
        if per_game.get(decision.game_id, 0) >= MAX_MATCHES_PER_GAME:
            continue
        per_game[decision.game_id] = per_game.get(decision.game_id, 0) + 1
        results.append(decision)
        if len(results) >= limit:
            break

    logger.debug(
        f"similar-decisions user={user_id}: {len(results)} of {len(candidates)} candidates "
        f"across {len(per_game)} games (floor={min_similarity})"
    )
    return results


def format_similar_decisions_for_context(decisions: Sequence[SimilarDecision]) -> str:
    """Coach-facing block. States absence explicitly when there is no history.

    Returning nothing is a legitimate and important answer: the coach must be able
    to say "this is new for you" instead of implying memory it does not have.
    """
    if not decisions:
        return (
            "## Similar past decisions\n"
            "None found: this situation is new for this player, so do not claim "
            "they have struggled with it before."
        )

    lines = ["## Similar past decisions (from this player's own games)"]
    for decision in decisions:
        what = decision.played_move or "?"
        better = decision.best_move or "?"
        pattern = f" (part of the '{decision.pattern_subtype}' pattern)" if decision.pattern_subtype else ""
        lines.append(
            f"- Game {decision.game_id}, move {decision.move_number} "
            f"({decision.match_kind.replace('_', ' ')}): played {what}, better was {better}, "
            f"{decision.outcome_text()}{pattern}"
        )
    if all(d.match_kind == "similar_features" for d in decisions):
        lines.append(
            "These are similar situations rather than the same position; say so."
        )
    return "\n".join(lines)
