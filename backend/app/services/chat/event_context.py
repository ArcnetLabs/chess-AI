"""Ranked player context for a specific position or event.

Why this module exists
----------------------
`assemble_coach_context` builds the longitudinal block used for general questions
and game analysis, but the intents that are *about a position* — explain this
move, analyse this position, compare these games — received only their Stockfish
block (see the phase 1 audit). The moments where a player asks "what should I do
here?" were therefore the moments with no player history at all.

This assembles the same intelligence for a single position:

* patterns relevant to *this* kind of position, ranked by measured impact;
* similar past decisions from the player's own games, with outcomes;
* coaching already offered for those patterns, and whether it moved.

Everything is ranked and budgeted. Blocks are dropped whole, lowest priority
first, rather than being truncated mid-sentence, and the honest "this is new for
you" answer is produced when nothing matches.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import chess
from loguru import logger
from sqlalchemy.orm import Session

from app.services.coaching.interventions import list_interventions
from app.services.patterns.pattern_service import list_user_patterns
from app.services.retrieval import (
    find_similar_decisions,
    find_similar_games,
    format_similar_games_for_context,
)

# Budgets: enough to ground a specific answer, small enough to leave room for the
# engine facts the answer is actually about.
MAX_PATTERNS = 4
MAX_SIMILAR = 3
MAX_SIMILAR_GAMES = 3
MAX_INTERVENTIONS = 3
MAX_BLOCK_CHARS = 2600

# The block states the rule it depends on. The coach's system prompt also carries
# grounding rules, so this is defence in depth rather than the only guard — but a
# block that hands the model pattern claims and history without saying they are
# the only admissible evidence is not self-describing, cannot be audited on its
# own, and would silently lose its constraint if it were ever reused elsewhere.
GROUNDING_RULE = (
    "Only the evidence below is admissible: do not invent chess evaluations, "
    "statistics, games or patterns beyond it."
)


def _features_for_fen(fen: str) -> Tuple[Optional[str], Optional[str], Dict, Optional[str]]:
    """Position key, structure key, features and phase for a FEN."""
    from app.services.analysis.position_features import (
        extract_features,
        material_balance,
        position_key,
        structure_key,
    )

    board = chess.Board(fen)
    features = extract_features(board)
    # A single position has no move number, so phase comes from material: this is
    # the material-aware notion the audit recommended, used here as a hint only.
    material = material_balance(board)
    features["material_balance"] = material if board.turn == chess.WHITE else -material
    simplified = features.get("simplified")
    phase = "endgame" if simplified else "middlegame"
    if board.fullmove_number <= 10:
        phase = "opening"
    return position_key(board), structure_key(board), features, phase


def _pattern_relevance(pattern, phase: Optional[str], concept: Optional[str]) -> float:
    """How relevant a pattern is to the position being discussed.

    Impact carries most of the weight — the coach should lead with what matters —
    but a pattern in the same phase, or about the same concept, is more relevant
    than an equally impactful one from an unrelated part of the game.
    """
    impact = float((pattern.evidence or {}).get("impact_score") or 0.0)
    score = impact
    signature = pattern.context_signature or ""
    if phase and signature.startswith(f"{phase}|"):
        score += 0.25
    if concept and pattern.pattern_type and concept in pattern.pattern_type:
        score += 0.1
    if pattern.is_strength:
        # Strengths inform tone, but the coach is looking for what to fix.
        score -= 0.15
    return round(score, 3)


def absence_context() -> str:
    """The exact text used when nothing matches this position.

    Public so evaluation probes can use the real string instead of a hand-copied
    imitation: a probe that re-types the message drifts from the system it claims
    to measure (it did — the copy was missing the grounding rule).
    """
    return (
        "## Player history for this position\n"
        f"{GROUNDING_RULE}\n"
        "Nothing on record for this kind of position yet. Coach from the engine "
        "facts alone, and say plainly that this situation is new for the player."
    )


def assemble_event_context(
    db: Session,
    user_id: int,
    *,
    fen: Optional[str] = None,
    phase: Optional[str] = None,
    concept: Optional[str] = None,
    exclude_game_id: Optional[int] = None,
) -> str:
    """Ranked player context for one position, or an explicit "nothing yet"."""
    if not fen:
        return ""

    try:
        position_key, structure_key, features, derived_phase = _features_for_fen(fen)
    except ValueError:
        logger.warning("assemble_event_context: unparseable FEN; skipping player context")
        return ""
    phase = phase or derived_phase

    blocks: List[Tuple[str, int, str]] = []  # (title, priority, body)

    # 1. Patterns relevant to this kind of position.
    patterns = list_user_patterns(db, user_id, limit=100)
    ranked = sorted(
        patterns, key=lambda p: -_pattern_relevance(p, phase, concept)
    )[:MAX_PATTERNS]
    if ranked:
        lines = []
        for pattern in ranked:
            rate = (
                f"{round(pattern.occurrence_rate * 100)}% of {pattern.opportunity_count} "
                f"similar decisions"
                if pattern.occurrence_rate is not None and pattern.opportunity_count
                else f"{pattern.occurrence_count} times"
            )
            trend = f", {pattern.trend_direction}" if pattern.trend_direction else ""
            kind = "strength" if pattern.is_strength else "recurring issue"
            lines.append(
                f"- {kind}: {pattern.pattern_description.split('.')[0]} "
                f"({rate}{trend}; pattern_id={pattern.id})"
            )
        blocks.append(
            ("## Recurring patterns in this kind of position", 1, "\n".join(lines))
        )

    # 2. Similar decisions from the player's own games.
    similar = find_similar_decisions(
        db,
        user_id,
        fen=fen,
        position_key=position_key,
        structure_key=structure_key,
        phase=phase,
        features=features,
        exclude_game_id=exclude_game_id,
        limit=MAX_SIMILAR,
    )
    if similar:
        lines = []
        for decision in similar:
            pattern = f" (part of '{decision.pattern_subtype}')" if decision.pattern_subtype else ""
            lines.append(
                f"- Game {decision.game_id} move {decision.move_number} "
                f"({decision.match_kind.replace('_', ' ')}): you played "
                f"{decision.played_move}, better was {decision.best_move}, "
                f"{decision.outcome_text()}{pattern}"
            )
        blocks.append(("## Similar positions from your own games", 2, "\n".join(lines)))

    # 2b. Whole games in this kind of position, with how they went. Anchored on
    # structure or exact position; it is silent when nothing genuinely matches,
    # which is the common case and the honest answer.
    games = find_similar_games(
        db,
        user_id,
        position_key=position_key,
        structure_key=structure_key,
        phase=phase,
        features=features,
        exclude_game_id=exclude_game_id,
        limit=MAX_SIMILAR_GAMES,
    )
    if games:
        block = format_similar_games_for_context(games)
        if block:
            heading, _, body = block.partition("\n")
            blocks.append((heading, 2, body))

    # 3. Coaching already offered for these patterns.
    interventions = list_interventions(db, user_id, limit=MAX_INTERVENTIONS)
    if interventions:
        lines = []
        for row in interventions:
            when = row.offered_at.date().isoformat() if row.offered_at else "earlier"
            lines.append(
                f"- {when}: {row.intervention_type.replace('_', ' ')}"
                f"{' — ' + row.title if row.title else ''} → {row.outcome}"
            )
        blocks.append(
            (
                "## Coaching already given (do not repeat it; build on it)",
                3,
                "\n".join(lines),
            )
        )

    if not blocks:
        return absence_context()

    # Budget: drop whole blocks, lowest priority first (higher number = lower
    # priority), rather than truncating a claim mid-sentence.
    blocks.sort(key=lambda item: item[1])
    while blocks:
        body = "\n\n".join(f"{title}\n{text}" for title, _priority, text in blocks)
        if len(body) <= MAX_BLOCK_CHARS or len(blocks) == 1:
            return f"{GROUNDING_RULE}\n\n{body}"
        dropped = blocks.pop()
        logger.debug(f"assemble_event_context: dropped block {dropped[0]!r} to fit budget")
    return ""


__all__ = ["assemble_event_context", "absence_context"]
