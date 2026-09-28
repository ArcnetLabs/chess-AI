"""What to work on, and where to practise it.

ChessRun is the coach, not the practice surface. Players do their reps on
ChessReps and ChessFlow, so the product's job is to work out *what* deserves
practice, say why in the player's own evidence, and hand off. This module owns
that mapping, so the coach's prompt, the API and the UI all describe the same
thing instead of each inventing its own wording and links.

Two rules worth stating, because breaking either turns coaching into advertising:

* **No invented content.** We do not have an integration yet, so we never name a
  drill, a course, a line or a URL on a partner platform. A plausible-looking link
  to something that may not exist is the same class of ungrounded claim the rest
  of the system is built to refuse.
* **A partner is suggested only when the fix genuinely lives there.** Repertoire
  memory belongs on ChessReps; calculation belongs on ChessFlow. When neither is a
  real fit, the focus is still recommended and no destination is named, rather
  than sending the player somewhere for the sake of a call to action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.pattern import PlayerPattern
from app.services.coaching.interventions import (
    INTERVENTION_PRACTICE,
    record_delivered_coaching,
)

# Partner keys are stable identifiers; names are what the player reads.
PARTNER_CHESSREPS = "chessreps"
PARTNER_CHESSFLOW = "chessflow"

DEFAULT_FOCUS_LIMIT = 3


@dataclass(frozen=True)
class PracticePartner:
    """A place practice happens, and what it is actually good for."""

    key: str
    name: str
    focus: str
    # We have no integration yet. Recording that honestly here keeps every surface
    # from implying otherwise, and gives the integration a single place to land.
    status: str = "coming_soon"
    url: Optional[str] = None


PRACTICE_PARTNERS: Dict[str, PracticePartner] = {
    PARTNER_CHESSREPS: PracticePartner(
        key=PARTNER_CHESSREPS,
        name="ChessReps",
        focus="spaced repetition of your opening repertoire",
    ),
    PARTNER_CHESSFLOW: PracticePartner(
        key=PARTNER_CHESSFLOW,
        name="ChessFlow",
        focus="guided calculation on the tactical themes you keep meeting",
    ),
}

# Event type -> (what the player should work on, where it belongs).
# Keyed by the event vocabulary the pattern engine already emits, so a new event
# type is a one-line addition rather than a new code path.
PRACTICE_BY_EVENT: Dict[str, tuple[str, Optional[str]]] = {
    "opening_deviation": ("your opening choices", PARTNER_CHESSREPS),
    "premature_pawn_push": ("your opening choices", PARTNER_CHESSREPS),
    "tactical_miss": ("spotting tactics when they appear", PARTNER_CHESSFLOW),
    "major_blunder": ("calculating before you commit", PARTNER_CHESSFLOW),
    "missed_win": ("converting the chances you get", PARTNER_CHESSFLOW),
    "failed_to_punish": ("punishing your opponent's mistakes", PARTNER_CHESSFLOW),
    "threat_unanswered": ("noticing your opponent's threats", PARTNER_CHESSFLOW),
    "conversion_failure": ("converting winning positions", PARTNER_CHESSFLOW),
    "endgame_technique_failure": ("your endgame technique", PARTNER_CHESSFLOW),
    "exchange_error": ("judging exchanges", None),
    "piece_activity_error": ("keeping your pieces active", None),
    "pawn_structure_error": ("your pawn structure decisions", None),
    "king_safety_error": ("keeping your king safe", None),
}


def _event_type(pattern: PlayerPattern) -> Optional[str]:
    """The event half of ``<event_type>__<context_signature>``."""
    subtype = pattern.pattern_subtype or ""
    if "__" in subtype:
        event_type = subtype.split("__", 1)[0]
        return event_type or None
    return None


def _evidence_sentence(pattern: PlayerPattern) -> str:
    """Why this is worth practising, using only stored measurements."""
    if pattern.occurrence_rate is not None and pattern.opportunity_count:
        share = round(pattern.occurrence_rate * 100)
        return (
            f"It came up in {share}% of the {pattern.opportunity_count} times you "
            f"were in that kind of position, across {pattern.affected_games_count} games."
        )
    return (
        f"It happened {pattern.occurrence_count} times across "
        f"{pattern.affected_games_count} games."
    )


def build_practice_focus(
    db: Session,
    user_id: int,
    *,
    limit: int = DEFAULT_FOCUS_LIMIT,
) -> List[Dict]:
    """The player's current practice focus, most important first.

    Ranked by how often the situation arises and how much it costs, not by
    severity alone: a rare critical error is one thing to fix, a recurring one is
    the thing to work on this week.
    """
    patterns = (
        db.query(PlayerPattern)
        .filter(
            PlayerPattern.user_id == user_id,
            PlayerPattern.is_strength.is_(False),
        )
        .all()
    )

    ranked = sorted(
        patterns,
        key=lambda p: (
            (p.occurrence_rate or 0.0),
            (p.occurrence_count or 0),
            (p.confidence_score or 0.0),
        ),
        reverse=True,
    )

    by_focus: Dict[str, Dict] = {}
    for pattern in ranked:
        event_type = _event_type(pattern)
        if event_type is None or event_type not in PRACTICE_BY_EVENT:
            # Legacy aggregate patterns ("endgame_major_swings") carry no event to
            # map. Recommending practice for them would mean guessing what to fix.
            continue
        focus, partner_key = PRACTICE_BY_EVENT[event_type]

        # Collapsed by focus, because a player reads this as "what to work on" and
        # the engine legitimately finds the same advice in several situations: real
        # data produced "your endgame technique" twice, from two contexts, which
        # reads as a broken page. The situations stay in pattern_ids — they remain
        # separate rows in the ledger, where outcomes are measured per pattern.
        existing = by_focus.get(focus)
        if existing is not None:
            existing["pattern_ids"].append(pattern.id)
            existing["situations"] = len(existing["pattern_ids"])
            continue
        if len(by_focus) >= limit:
            continue

        partner = PRACTICE_PARTNERS.get(partner_key) if partner_key else None
        by_focus[focus] = {
            "pattern_id": pattern.id,
            "pattern_ids": [pattern.id],
            "situations": 1,
            "focus": focus,
            "why": _evidence_sentence(pattern),
            "context": pattern.context_signature,
            "severity": pattern.severity,
            "trend": pattern.trend_direction,
            "occurrences": pattern.occurrence_count,
            "opportunities": pattern.opportunity_count,
            "partner": (
                {
                    "key": partner.key,
                    "name": partner.name,
                    "focus": partner.focus,
                    "status": partner.status,
                    "url": partner.url,
                }
                if partner
                else None
            ),
        }
    return list(by_focus.values())


def offer_practice_focus(db: Session, user_id: int, *, limit: int = DEFAULT_FOCUS_LIMIT) -> List[Dict]:
    """Return the focus *and* record that it was recommended.

    Recording is what makes "have I taught you this, and did it work?" answerable:
    the ledger row is the moment coaching was delivered, and the outcome machinery
    measures the pattern's rate after it. One row per *situation* — the page may
    collapse two situations into one line of advice, but each is measured against
    its own pattern. Duplicate offers are skipped by the ledger itself, so this is
    safe to call on every pattern run.
    """
    items = build_practice_focus(db, user_id, limit=limit)
    recorded = 0
    for item in items:
        for pattern_id in item["pattern_ids"]:
            row = record_delivered_coaching(
                db,
                user_id,
                pattern_id=pattern_id,
                intervention_type=INTERVENTION_PRACTICE,
                title=item["focus"],
                payload={
                    "focus": item["focus"],
                    "partner": item["partner"]["key"] if item["partner"] else None,
                    "opportunities": item["opportunities"],
                    "situations": item["situations"],
                },
                commit=False,
            )
            if row is not None:
                recorded += 1
    if recorded:
        db.commit()
        logger.info(
            f"Offered practice focus to user_id={user_id}: "
            f"{recorded} new recommendation(s), {len(items)} in focus"
        )
    return items
