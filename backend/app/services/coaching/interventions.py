"""Coaching memory: record what was offered, and measure what happened.

Design decisions worth stating, because they are what make this honest:

* An outcome is **measured, never claimed**: it is the pattern's occurrence rate
  in the games after the intervention compared with the games before it, using the
  same decision series the pattern engine uses.
* Having too little evidence is a first-class answer (``unknown``): an
  intervention offered yesterday cannot be judged.
* "Resolved" requires the pattern to have genuinely stopped appearing in enough
  later games — not merely a low rate.
* Interventions are never deleted when their pattern is pruned: the record that
  coaching happened is history, and the pattern only exists to explain it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from loguru import logger
from sqlalchemy.orm import Session

from app.models.coaching_intervention import CoachingIntervention
from app.models.pattern import PlayerPattern
from app.services.patterns.event_pattern_detector import Decision, load_decisions

# Outcome states.
OUTCOME_UNKNOWN = "unknown"
OUTCOME_IMPROVING = "improving"
OUTCOME_PERSISTENT = "persistent"
OUTCOME_RESOLVED = "resolved"
OUTCOME_WORSENED = "worsening"

# Games needed after the intervention before an outcome is claimed at all.
MIN_GAMES_AFTER = 3
# Rate ratio thresholds, matching the pattern engine's trend classification.
IMPROVING_RATIO = 0.6
WORSENING_RATIO = 1.5

INTERVENTION_DRILL = "drill"
INTERVENTION_VARIATION = "variation_study"
INTERVENTION_CONCEPT = "concept_explanation"
INTERVENTION_EXERCISE = "position_exercise"

VALID_TYPES = (
    INTERVENTION_DRILL,
    INTERVENTION_VARIATION,
    INTERVENTION_CONCEPT,
    INTERVENTION_EXERCISE,
)


def record_intervention(
    db: Session,
    user_id: int,
    *,
    intervention_type: str,
    pattern_id: Optional[int] = None,
    pattern_subtype: Optional[str] = None,
    context_signature: Optional[str] = None,
    concept: Optional[str] = None,
    title: Optional[str] = None,
    payload: Optional[Dict] = None,
    source: str = "coach",
    session_id: Optional[str] = None,
    offered_at: Optional[datetime] = None,
    commit: bool = True,
) -> CoachingIntervention:
    """Record an intervention offered to the player.

    When only ``pattern_id`` is given, the pattern's subtype, context and concept
    are copied across, so the outcome can be measured later even if the pattern
    row is pruned (``pattern_id`` becomes null but the descriptive fields remain).
    """
    if intervention_type not in VALID_TYPES:
        raise ValueError(
            f"unknown intervention_type {intervention_type!r}; expected one of {VALID_TYPES}"
        )

    if pattern_id is not None and pattern_subtype is None:
        pattern = db.query(PlayerPattern).filter(PlayerPattern.id == pattern_id).first()
        if pattern is not None:
            pattern_subtype = pattern_subtype or pattern.pattern_subtype
            context_signature = context_signature or pattern.context_signature
            concept = concept or pattern.pattern_type

    row = CoachingIntervention(
        user_id=user_id,
        pattern_id=pattern_id,
        intervention_type=intervention_type,
        concept=concept,
        pattern_subtype=pattern_subtype,
        context_signature=context_signature,
        title=title,
        payload=payload or None,
        source=source,
        session_id=session_id,
        offered_at=offered_at or datetime.now(timezone.utc),
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    logger.info(
        f"Recorded intervention {intervention_type} for user_id={user_id} "
        f"pattern={pattern_subtype or pattern_id}"
    )
    return row


def _pattern_from_subtype(subtype: Optional[str]) -> Optional[tuple[str, str]]:
    """Recover ``(event_type, context_signature)`` from a stored subtype.

    The engine names subtypes ``<event_type>__<context_signature>``, so the
    evidence a pattern was built from can be recovered from the name alone — which
    is what lets outcomes survive pattern pruning.
    """
    if not subtype or "__" not in subtype:
        return None
    event_type, _, context = subtype.partition("__")
    if not event_type or not context:
        return None
    return event_type, context


def _series_for(
    decisions: Sequence[Decision], event_type: str, context: str
) -> List[Decision]:
    return [d for d in decisions if d.context == context]


def _rate_of(
    decisions: Sequence[Decision], event_type: str
) -> tuple[int, int, Optional[float]]:
    opportunities = len(decisions)
    occurrences = sum(1 for d in decisions if event_type in d.event_types)
    if opportunities == 0:
        return 0, 0, None
    return occurrences, opportunities, round(occurrences / opportunities, 4)


def evaluate_intervention_outcome(
    intervention: CoachingIntervention,
    decisions: Sequence[Decision],
) -> Dict:
    """Measure one intervention's outcome from the decision series.

    Returns the outcome and the evidence behind it; does not write anything.
    """
    parsed = _pattern_from_subtype(intervention.pattern_subtype)
    if parsed is None:
        return {
            "outcome": OUTCOME_UNKNOWN,
            "reason": "intervention is not tied to a measurable pattern",
        }
    event_type, context = parsed

    offered_at = intervention.offered_at
    if offered_at is not None and offered_at.tzinfo is None:
        offered_at = offered_at.replace(tzinfo=timezone.utc)

    before: List[Decision] = []
    after: List[Decision] = []
    for decision in _series_for(decisions, event_type, context):
        if offered_at is None or decision.game_end_time is None:
            before.append(decision)
            continue
        end = decision.game_end_time
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        (after if end > offered_at else before).append(decision)

    games_after = len({d.game_id for d in after})
    occurrences_before, opportunities_before, rate_before = _rate_of(before, event_type)
    occurrences_after, opportunities_after, rate_after = _rate_of(after, event_type)

    evidence = {
        "event_type": event_type,
        "context_signature": context,
        "before": {
            "occurrences": occurrences_before,
            "opportunities": opportunities_before,
            "rate": rate_before,
        },
        "after": {
            "occurrences": occurrences_after,
            "opportunities": opportunities_after,
            "rate": rate_after,
        },
        "games_after": games_after,
        "thresholds": {
            "min_games_after": MIN_GAMES_AFTER,
            "improving_ratio": IMPROVING_RATIO,
            "worsening_ratio": WORSENING_RATIO,
        },
    }

    if games_after < MIN_GAMES_AFTER or rate_before is None or rate_after is None:
        return {
            "outcome": OUTCOME_UNKNOWN,
            "reason": "not enough games since the intervention to judge",
            "evidence": evidence,
        }

    if occurrences_before == 0:
        # The pattern was not actually present before the intervention, so there
        # was nothing to fix. Calling this "resolved" would credit the coaching
        # with a change that never happened.
        evidence["note"] = "pattern had no occurrences before the intervention"
        return {"outcome": OUTCOME_UNKNOWN, "reason": "nothing to measure", "evidence": evidence}

    if occurrences_after == 0:
        outcome = OUTCOME_RESOLVED
    else:
        ratio = rate_after / rate_before
        evidence["ratio"] = round(ratio, 3)
        if ratio <= IMPROVING_RATIO:
            outcome = OUTCOME_IMPROVING
        elif ratio >= WORSENING_RATIO:
            outcome = OUTCOME_WORSENED
        else:
            outcome = OUTCOME_PERSISTENT

    return {"outcome": outcome, "evidence": evidence}


def evaluate_intervention_outcomes(db: Session, user_id: int) -> Dict[str, int]:
    """Refresh outcomes for a user's open interventions.

    Called after pattern detection so outcomes track the newest games. Only
    interventions whose outcome might have changed are recomputed: resolved and
    worsening ones are left alone, because re-measuring them every run would
    rewrite history on the strength of one new game.
    """
    open_rows = (
        db.query(CoachingIntervention)
        .filter(
            CoachingIntervention.user_id == user_id,
            CoachingIntervention.outcome.in_([OUTCOME_UNKNOWN, OUTCOME_IMPROVING,
                                              OUTCOME_PERSISTENT]),
        )
        .all()
    )
    if not open_rows:
        return {}

    decisions = load_decisions(db, user_id)
    if not decisions:
        return {}

    counts: Dict[str, int] = {}
    evaluated_at = datetime.now(timezone.utc)
    for intervention in open_rows:
        result = evaluate_intervention_outcome(intervention, decisions)
        outcome = result["outcome"]
        counts[outcome] = counts.get(outcome, 0) + 1
        if outcome != OUTCOME_UNKNOWN or result.get("evidence"):
            intervention.outcome = outcome
            intervention.outcome_evaluated_at = evaluated_at
            intervention.outcome_evidence = result.get("evidence")
    db.commit()
    logger.info(f"Evaluated {len(open_rows)} interventions for user_id={user_id}: {counts}")
    return counts


def list_interventions(
    db: Session,
    user_id: int,
    *,
    limit: int = 20,
    unresolved_only: bool = False,
) -> List[CoachingIntervention]:
    """Most recent interventions first."""
    query = db.query(CoachingIntervention).filter(CoachingIntervention.user_id == user_id)
    if unresolved_only:
        query = query.filter(
            CoachingIntervention.outcome.in_([OUTCOME_UNKNOWN, OUTCOME_PERSISTENT,
                                              OUTCOME_IMPROVING])
        )
    return query.order_by(CoachingIntervention.offered_at.desc()).limit(limit).all()


def coaching_history_summary(
    db: Session, user_id: int, *, limit: int = 10
) -> List[Dict]:
    """Compact history for the profile snapshot and coaching context.

    Deliberately small: the coach needs to know what was tried and whether it
    worked, not the full payload of every drill ever generated.
    """
    rows = list_interventions(db, user_id, limit=limit)
    return [
        {
            "intervention_type": row.intervention_type,
            "pattern_subtype": row.pattern_subtype,
            "title": (row.title or "")[:120] or None,
            "offered_at": row.offered_at.isoformat() if row.offered_at else None,
            "outcome": row.outcome,
            "outcome_rate_after": (
                (row.outcome_evidence or {}).get("after", {}).get("rate")
                if row.outcome_evidence
                else None
            ),
            "outcome_rate_before": (
                (row.outcome_evidence or {}).get("before", {}).get("rate")
                if row.outcome_evidence
                else None
            ),
        }
        for row in rows
    ]
