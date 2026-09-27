"""Event-driven, context-aware pattern detection.

This is the layer the product principle depends on. The existing detectors count
labels and phase averages; this one asks a different question: *in this kind of
situation, how often does this player make this kind of decision?*

Method, per ``(event_type, context_signature)`` group:

* **Denominator first.** Every user move in the same context is an *opportunity*.
  Counting events without opportunities cannot distinguish "made this mistake
  seven times" from "made it seven times out of nine hundred", which is noise.
* **Similarity, not equality.** Grouping is by the situation (phase, material
  state, complexity, pawn structure, whether the opponent's move created the
  problem), so unrelated mistakes of the same label do not merge.
* **Evidence, always.** Rate, opportunities, window, mean damage and example
  event ids are persisted, so any claim a coach makes can be re-derived.
* **Trend from the data**, not from run history: the decision series is split by
  game recency, so "improving" means the recent games are measurably better.
* **Strengths are detected too**, by the same standard, so the profile is not a
  list of failures.

No LLM and no engine call: everything is computed from ``chess_events`` and
``game_moves``, which are themselves engine-derived facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from app.models.chess_event import ChessEvent
from app.models.game import Game
from app.models.game_move import GameMove

from .context_signature import context_signature, describe_context, material_state
from .types import DetectedPattern, PatternOccurrenceInput, PatternSeverity

DETECTOR_ID = "event_context"
DETECTOR_VERSION = 1

# A weakness needs repetition before it is coaching-worthy.
MIN_OCCURRENCES = 3
MIN_DISTINCT_GAMES = 3
# Below this opportunity count a rate is not trustworthy, however striking.
MIN_OPPORTUNITIES = 8

# Trend classification thresholds (ratio of recent rate to earlier rate).
IMPROVING_RATIO = 0.6
WORSENING_RATIO = 1.5

# A phase is a strength when the player rarely makes *serious* errors there.
# "Serious" means a high- or critical-severity event, because the vocabulary also
# fires for small slips and counting those would disqualify every phase.
STRENGTH_MIN_OPPORTUNITIES = 25
STRENGTH_MAX_RATE = 0.12

# Concepts mapped to the kind of practice that addresses them. The recommendation
# chain is pattern -> concept -> intervention; this is the middle link.
CONCEPT_DRILLS: Dict[str, str] = {
    "tactics": "tactical_motif_training",
    "calculation": "candidate_move_calculation",
    "king_safety": "king_safety_patterns",
    "piece_activity": "piece_activity_positions",
    "pawn_structure": "pawn_structure_plans",
    "endgame_technique": "endgame_technique",
    "conversion": "winning_position_conversion",
    "opening": "opening_principles",
    "exchanges": "exchange_evaluation",
    "threat_awareness": "threat_detection",
    "time_management": "time_management",
}

_EVENT_LABELS: Dict[str, str] = {
    "major_blunder": "a serious blunder",
    "tactical_miss": "missing a tactic that was there",
    "missed_win": "letting a winning position slip",
    "conversion_failure": "failing to convert an advantage",
    "endgame_technique_failure": "an endgame technique error",
    "king_safety_error": "leaving your king exposed",
    "piece_activity_error": "letting your pieces go passive",
    "pawn_structure_error": "a positional slip",
    "exchange_error": "getting an exchange wrong",
    "threat_unanswered": "not answering the opponent's threat",
    "failed_to_punish": "not punishing the opponent's mistake",
    "opening_deviation": "an opening inaccuracy",
    "premature_pawn_push": "a pawn move that weakened your position",
    "time_pressure_error": "a time-pressure error",
}


def _severity_from_damage(mean_cp_loss: float, rate: float) -> PatternSeverity:
    """Severity from measured damage and how often it actually happens.

    Both matter: a rare but ruinous error and a frequent small one are different
    coaching problems, and neither should be judged on counts alone.
    """
    if mean_cp_loss >= 400 and rate >= 0.10:
        return PatternSeverity.CRITICAL
    if mean_cp_loss >= 300 or rate >= 0.15:
        return PatternSeverity.HIGH
    if mean_cp_loss >= 180 or rate >= 0.08:
        return PatternSeverity.MEDIUM
    return PatternSeverity.LOW


def _confidence(occurrences: int, games: int, opportunities: int, rate: float) -> float:
    """Confidence in the pattern, not in the player.

    Sample size dominates, because a striking rate over four decisions is not
    evidence. The rate contributes only once there is enough of it to matter.
    """
    sample = min(1.0, opportunities / 40.0)
    breadth = min(1.0, games / 6.0)
    volume = min(1.0, occurrences / 6.0)
    strength = min(1.0, rate / 0.25)
    return round(min(0.99, 0.35 * sample + 0.25 * breadth + 0.20 * volume + 0.20 * strength), 2)


def _classify_trend(
    recent_rate: Optional[float],
    older_rate: Optional[float],
    *,
    recent_occurrences: int,
    older_occurrences: int,
) -> str:
    """Classify direction from the decision series, split by game recency."""
    if older_occurrences == 0 and recent_occurrences > 0:
        return "new"
    if recent_occurrences == 0 and older_occurrences > 0:
        return "resolved"
    if recent_rate is None or older_rate is None or older_rate == 0:
        return "persistent"
    ratio = recent_rate / older_rate
    if ratio <= IMPROVING_RATIO:
        return "improving"
    if ratio >= WORSENING_RATIO:
        return "worsening"
    return "persistent"


@dataclass(eq=False)
class Decision:
    """One user decision, classified by context and by whether it went wrong.

    ``eq=False`` keeps equality and hashing identity-based: decisions are mutable
    records and are compared by which object they are (sets of them are used to
    split a series into recent and older halves), never by value.
    """

    game_id: int
    game_order: int  # recency rank: 0 = most recent game
    event_types: Tuple[str, ...] = ()
    cp_loss: float = 0.0
    phase: Optional[str] = None
    context: str = ""
    game_result: Optional[str] = None
    move_number: int = 0
    move_id: Optional[int] = None
    fen_before: Optional[str] = None
    played_move: Optional[str] = None
    best_move: Optional[str] = None
    eval_before: Optional[float] = None
    eval_after: Optional[float] = None
    event_ids: Tuple[int, ...] = ()
    structure_key: Optional[str] = None
    serious_event_types: Tuple[str, ...] = ()

    @property
    def has_serious_event(self) -> bool:
        """Whether a high- or critical-severity event fired on this decision.

        The event vocabulary fires liberally — several detectors can trigger on
        one move — so "made a mistake here" is far too common a bar for a
        *strength*. Serious events are the ones that decide games.
        """
        return bool(self.serious_event_types)


@dataclass
class _Group:
    decisions: List[Decision] = field(default_factory=list)

    @property
    def errors(self) -> List[Decision]:
        return [d for d in self.decisions if d.event_types]


def _load_decisions(db: Session, user_id: int, game_limit: Optional[int]) -> List[Decision]:
    """Load every user move with its context and any events attached to it.

    One pass over ``game_moves`` (user moves only) joined to events, ordered by
    game recency, so opportunities and occurrences come from the same source and
    cannot drift apart.
    """
    games_query = (
        db.query(Game.id, Game.end_time, Game.winner)
        .join(GameMove, GameMove.game_id == Game.id)
        .filter(Game.user_id == user_id)
        .distinct()
        .order_by(Game.end_time.desc().nullslast())
    )
    games = games_query.all()
    if game_limit:
        games = games[:game_limit]
    if not games:
        return []

    order = {game_id: rank for rank, (game_id, _end, _winner) in enumerate(games)}
    winners = {game_id: winner for (game_id, _end, winner) in games}
    game_ids = list(order)

    all_moves = (
        db.query(GameMove)
        .filter(GameMove.user_id == user_id, GameMove.game_id.in_(game_ids))
        .order_by(GameMove.game_id, GameMove.ply)
        .all()
    )
    moves = [m for m in all_moves if m.is_user_move]
    # Opponent damage by (game, ply) — needed to know whether the previous move
    # actually created the problem rather than merely preceding it.
    opponent_damage = {
        (m.game_id, m.ply): float(m.cp_loss or 0.0) for m in all_moves if not m.is_user_move
    }

    events_by_move: Dict[int, List[ChessEvent]] = {}
    for event in (
        db.query(ChessEvent)
        .filter(ChessEvent.user_id == user_id, ChessEvent.game_id.in_(game_ids))
        .all()
    ):
        events_by_move.setdefault(event.move_id, []).append(event)

    decisions: List[Decision] = []
    for move in moves:
        events = events_by_move.get(move.id, [])
        features = move.features or {}
        decisions.append(
            Decision(
                game_id=move.game_id,
                game_order=order.get(move.game_id, 0),
                event_types=tuple(sorted({e.event_type for e in events})),
                serious_event_types=tuple(
                    sorted(
                        {
                            e.event_type
                            for e in events
                            if e.severity in ("high", "critical")
                        }
                    )
                ),
                cp_loss=float(move.cp_loss or 0.0),
                phase=move.phase,
                context=context_signature(
                    phase=move.phase,
                    features=features,
                    structure_key=move.structure_key,
                    has_opponent_trigger=_is_triggered(move, features, opponent_damage),
                ),
                game_result=winners.get(move.game_id),
                move_number=move.move_number,
                move_id=move.id,
                structure_key=move.structure_key,
                fen_before=move.fen_before,
                played_move=move.move_uci,
                best_move=move.best_move_uci,
                eval_before=move.eval_before_cp,
                eval_after=move.eval_after_cp,
                event_ids=tuple(sorted(e.id for e in events)),
            )
        )
    return decisions


# An opponent move that lost this much is what "the opponent created a problem"
# means; below it, the opponent simply moved.
TRIGGER_OPPONENT_CP_LOSS = 150.0


def _is_triggered(move: GameMove, features: Dict, opponent_damage: Dict) -> bool:
    """Whether the opponent's play created the situation, in a useful sense.

    Two ways that can be true, and both are facts about the position rather than
    about the move order:

    * the mover had a piece hanging when they moved — a threat was pending, so
      the decision was forced or should have been;
    * the opponent's previous move was itself an error — the mover had a chance
      to punish it.

    "An opponent moved before this one" is *not* the test: that is true for every
    move after the first and classified almost the whole dataset as triggered.
    """
    if features.get("mover_hanging"):
        return True
    previous = opponent_damage.get((move.game_id, move.ply - 1))
    return previous is not None and previous >= TRIGGER_OPPONENT_CP_LOSS


def _split_by_recency(
    decisions: Sequence[Decision],
) -> Tuple[List[Decision], List[Decision]]:
    """Split into (recent half, older half) by game recency.

    Games, not decisions: a long game should not outweigh a short one when asking
    whether the player is improving.
    """
    orders = sorted({d.game_order for d in decisions})
    if len(orders) < 2:
        return list(decisions), []
    midpoint = len(orders) // 2
    recent_orders = set(orders[:midpoint])
    recent = [d for d in decisions if d.game_order in recent_orders]
    older = [d for d in decisions if d.game_order not in recent_orders]
    return recent, older


def _rate(errors: int, opportunities: int) -> Optional[float]:
    if opportunities == 0:
        return None
    return round(errors / opportunities, 4)


def _top_structures(decisions: Iterable[Decision], limit: int = 3) -> List[Dict]:
    """Most common pawn-structure buckets among a set of decisions."""
    counts: Dict[str, int] = {}
    for decision in decisions:
        if decision.structure_key:
            counts[decision.structure_key] = counts.get(decision.structure_key, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return [{"structure_key": key, "occurrences": count} for key, count in ranked]


def _occurrence_inputs(
    errors: Iterable[Decision], *, context: str, event_type: str
) -> List[PatternOccurrenceInput]:
    """Occurrence rows carrying the position and the decision made in it.

    ``best_eval`` is the evaluation *before* the move: that is the engine's value
    with best play, which is exactly what the player was choosing from.
    """
    return [
        PatternOccurrenceInput(
            game_id=d.game_id,
            move_number=d.move_number,
            game_phase=d.phase,
            fen_before=d.fen_before,
            user_move=d.played_move,
            best_move=d.best_move,
            user_eval=d.eval_after,
            best_eval=d.eval_before,
            eval_delta=round(d.cp_loss, 1),
            context_description=describe_context(context),
            detector_metadata={
                "detector": DETECTOR_ID,
                "version": DETECTOR_VERSION,
                "event_type": event_type,
                "context_signature": context,
                # Consumed by the persistence layer to link the occurrence back
                # to the move and event it came from, so a claim can be walked
                # down to the engine evaluation behind it.
                "move_id": d.move_id,
                "event_id": d.event_ids[0] if d.event_ids else None,
            },
        )
        for d in errors
    ]


def _impact_score(
    *, severity: PatternSeverity, rate: float, confidence: float, games: int, mean_cp_loss: float
) -> float:
    """Rank patterns so a coach can act on the few that matter.

    Detection is deliberately inclusive — every context with enough evidence is
    recorded, because the evidence is the product's asset — but a player needs
    *one* thing to work on. Impact weights how often it happens, how much damage
    it does, how sure the system is, and how broadly it shows up, so the top of
    the list is the highest-leverage improvement rather than the longest list.

    Range 0-1; consumers should present a small top-N and keep the rest as
    supporting evidence.
    """
    severity_weight = {
        PatternSeverity.LOW: 0.35,
        PatternSeverity.MEDIUM: 0.6,
        PatternSeverity.HIGH: 0.85,
        PatternSeverity.CRITICAL: 1.0,
    }.get(severity, 0.5)
    frequency = min(1.0, rate / 0.3)
    breadth = min(1.0, games / 20.0)
    damage = min(1.0, mean_cp_loss / 500.0)
    score = (
        0.35 * severity_weight
        + 0.25 * frequency
        + 0.20 * confidence
        + 0.10 * breadth
        + 0.10 * damage
    )
    return round(min(1.0, score), 3)


def detect_context_patterns(
    decisions: Sequence[Decision],
    *,
    pattern_type: str = "decision_pattern",
) -> List[DetectedPattern]:
    """Weakness patterns: recurring wrong decisions in a recurring situation."""
    groups: Dict[Tuple[str, str], _Group] = {}
    for decision in decisions:
        for event_type in decision.event_types:
            groups.setdefault((event_type, decision.context), _Group()).decisions.append(decision)

    patterns: List[DetectedPattern] = []
    for (event_type, context), group in sorted(groups.items()):
        # Every decision in this context is an opportunity, whether or not it
        # went wrong — this is the denominator that makes the rate meaningful.
        opportunities = [d for d in decisions if d.context == context]
        errors = group.errors
        distinct_games = {d.game_id for d in errors}
        if len(errors) < MIN_OCCURRENCES or len(distinct_games) < MIN_DISTINCT_GAMES:
            continue
        if len(opportunities) < MIN_OPPORTUNITIES:
            continue

        rate = _rate(len(errors), len(opportunities)) or 0.0
        mean_cp_loss = sum(d.cp_loss for d in errors) / len(errors)

        # Trend must be measured against the timeline of *decisions*, not of the
        # errors themselves: splitting only the errors would compare "the errors
        # I made early" with "the errors I made late" and always look flat.
        recent_opportunities, older_opportunities = _split_by_recency(opportunities)
        recent_errors = [d for d in recent_opportunities if d.event_types]
        older_errors = [d for d in older_opportunities if d.event_types]
        trend = _classify_trend(
            _rate(len(recent_errors), len(recent_opportunities)),
            _rate(len(older_errors), len(older_opportunities)),
            recent_occurrences=len(recent_errors),
            older_occurrences=len(older_errors),
        )

        subtype = f"{event_type}__{context}"[:120]
        label = _EVENT_LABELS.get(event_type, event_type.replace("_", " "))
        severity = _severity_from_damage(mean_cp_loss, rate)
        confidence = _confidence(
            len(errors), len(distinct_games), len(opportunities), rate
        )
        impact = _impact_score(
            severity=severity,
            rate=rate,
            confidence=confidence,
            games=len(distinct_games),
            mean_cp_loss=mean_cp_loss,
        )
        patterns.append(
            DetectedPattern(
                pattern_type=pattern_type,
                pattern_subtype=subtype,
                severity=severity,
                confidence_score=confidence,
                occurrence_count=len(errors),
                affected_games_count=len(distinct_games),
                affected_games_ratio=round(len(distinct_games) / max(1, len(opportunities)), 4),
                pattern_description=(
                    f"Recurring pattern: {label} {describe_context(context)}. "
                    f"Seen {len(errors)} times across {len(distinct_games)} games, "
                    f"in {round(rate * 100)}% of the {len(opportunities)} times you faced "
                    f"this kind of position."
                ),
                example_positions=[
                    {
                        "game_id": d.game_id,
                        "move_number": d.move_number,
                        "phase": d.phase,
                    }
                    for d in sorted(errors, key=lambda x: -x.cp_loss)[:5]
                ],
                occurrences=_occurrence_inputs(errors, context=context, event_type=event_type),
                trend_direction=trend,
                is_strength=False,
                recommended_drill_type=CONCEPT_DRILLS.get(
                    event_type.replace("_error", "").replace("_miss", ""), None
                )
                or CONCEPT_DRILLS.get("calculation"),
                context_signature=context,
                opportunity_count=len(opportunities),
                occurrence_rate=rate,
                detector_id=DETECTOR_ID,
                detector_version=DETECTOR_VERSION,
                evidence={
                    "detector": DETECTOR_ID,
                    "version": DETECTOR_VERSION,
                    "event_type": event_type,
                    "context_signature": context,
                    "occurrences": len(errors),
                    "opportunities": len(opportunities),
                    "occurrence_rate": rate,
                    "distinct_games": len(distinct_games),
                    "mean_cp_loss": round(mean_cp_loss, 1),
                    "impact_score": impact,
                    "recent": {
                        "occurrences": len(recent_errors),
                        "opportunities": len(recent_opportunities),
                        "rate": _rate(len(recent_errors), len(recent_opportunities)),
                    },
                    "older": {
                        "occurrences": len(older_errors),
                        "opportunities": len(older_opportunities),
                        "rate": _rate(len(older_errors), len(older_opportunities)),
                    },
                    "example_event_ids": sorted(
                        {eid for d in errors for eid in d.event_ids}
                    )[:10],
                    # The specific pawn structures this keeps happening in, as
                    # detail rather than as a grouping key (see context_signature).
                    "structures": _top_structures(errors),
                    "thresholds": {
                        "min_occurrences": MIN_OCCURRENCES,
                        "min_games": MIN_DISTINCT_GAMES,
                        "min_opportunities": MIN_OPPORTUNITIES,
                    },
                },
            )
        )
    return patterns


def detect_strengths(decisions: Sequence[Decision]) -> List[DetectedPattern]:
    """Strengths, held to the same evidence standard as weaknesses.

    A phase counts as a strength when significant errors are rare there *and* the
    player has actually spent enough decisions in it for that to mean something.
    """
    patterns: List[DetectedPattern] = []
    by_phase: Dict[str, List[Decision]] = {}
    for decision in decisions:
        if decision.phase:
            by_phase.setdefault(decision.phase, []).append(decision)

    for phase, phase_decisions in sorted(by_phase.items()):
        opportunities = len(phase_decisions)
        if opportunities < STRENGTH_MIN_OPPORTUNITIES:
            continue
        # Serious errors only: the event vocabulary fires liberally, so counting
        # every event would make no phase look solid.
        errors = [d for d in phase_decisions if d.has_serious_event]
        rate = len(errors) / opportunities
        if rate > STRENGTH_MAX_RATE:
            continue
        games = {d.game_id for d in phase_decisions}
        patterns.append(
            DetectedPattern(
                pattern_type="phase_strength",
                pattern_subtype=f"solid_{phase}",
                severity=PatternSeverity.LOW,
                confidence_score=round(min(0.95, 0.4 + min(0.4, opportunities / 100) + (1 - min(1.0, rate / STRENGTH_MAX_RATE)) * 0.2), 2),
                occurrence_count=len(errors),
                affected_games_count=len(games),
                affected_games_ratio=round(len(games) / max(1, opportunities), 4),
                pattern_description=(
                    f"Strength: your {phase} play holds up — only {len(errors)} significant "
                    f"errors in {opportunities} decisions across {len(games)} games."
                ),
                example_positions=[],
                occurrences=[],
                trend_direction=None,
                is_strength=True,
                recommended_drill_type=None,
                context_signature=None,
                opportunity_count=opportunities,
                occurrence_rate=round(rate, 4),
                detector_id=DETECTOR_ID,
                detector_version=DETECTOR_VERSION,
                evidence={
                    "detector": DETECTOR_ID,
                    "version": DETECTOR_VERSION,
                    "phase": phase,
                    "opportunities": opportunities,
                    "significant_errors": len(errors),
                    "error_rate": round(rate, 4),
                    "games": len(games),
                    "thresholds": {
                        "min_opportunities": STRENGTH_MIN_OPPORTUNITIES,
                        "max_error_rate": STRENGTH_MAX_RATE,
                    },
                },
            )
        )
    return patterns


# Detection is inclusive: every context with enough evidence is computed, because
# the evidence is the asset. Persisting is not — a real account produced 168
# weaknesses, and a profile that lists 168 things is the same as listing none.
# The tail is deterministic and cheap to recompute, so only the actionable head
# is stored; strengths are always kept.
MAX_PERSISTED_CONTEXT_PATTERNS = 25


def detect_event_patterns(
    db: Session,
    user_id: int,
    *,
    game_limit: Optional[int] = None,
) -> Tuple[List[DetectedPattern], int]:
    """Run the context-aware detectors for a user.

    Returns ``(patterns, decisions_considered)``, ordered by impact so the first
    entry is the highest-leverage thing to work on, and capped to the actionable
    head for persistence.
    """
    decisions = _load_decisions(db, user_id, game_limit)
    if not decisions:
        return [], 0

    detected = detect_context_patterns(decisions) + detect_strengths(decisions)
    detected.sort(
        key=lambda p: (
            not p.is_strength,
            -(p.evidence.get("impact_score") or 0.0),
            -p.confidence_score,
        )
    )

    strengths = [p for p in detected if p.is_strength]
    weaknesses = [p for p in detected if not p.is_strength]
    kept = strengths + weaknesses[:MAX_PERSISTED_CONTEXT_PATTERNS]

    logger.info(
        f"Event pattern detection user_id={user_id}: {len(detected)} patterns "
        f"from {len(decisions)} decisions ({len(kept)} kept: "
        f"{len(strengths)} strengths + top {len(kept) - len(strengths)} weaknesses)"
    )
    return kept, len(decisions)
