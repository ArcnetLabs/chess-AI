"""Tests for the ranked player-context block used by position-centric intents.

The properties that matter:

* a position-centric answer gets the player's relevant patterns, similar past
  decisions and prior coaching — the gap the audit found;
* relevance ranking prefers patterns from the same phase and of higher impact;
* absence is stated, so the coach can say "this is new for you";
* budgets drop whole blocks rather than truncating claims;
* a failure in this path never costs the engine-grounded answer.
"""

import chess
import pytest

from app.models.pattern import PlayerPattern
from app.models.user import User
from app.services.chat.event_context import (
    GROUNDING_RULE,
    MAX_BLOCK_CHARS,
    MAX_PATTERNS,
    absence_context,
    assemble_event_context,
)

START_FEN = chess.STARTING_FEN
AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


@pytest.fixture
def user(db):
    row = User(
        supabase_user_id="event-context-user",
        email="event-context@chessrun.local",
        chesscom_username="event_context_tester",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def add_pattern(
    db,
    user_id: int,
    *,
    subtype: str,
    context: str,
    impact: float,
    rate: float = 0.3,
    opportunities: int = 40,
    trend: str = "persistent",
    is_strength: bool = False,
) -> PlayerPattern:
    row = PlayerPattern(
        user_id=user_id,
        pattern_type="decision_pattern",
        pattern_subtype=subtype,
        severity="high",
        confidence_score=0.9,
        occurrence_count=12,
        affected_games_count=6,
        affected_games_ratio=0.2,
        pattern_description=f"Recurring pattern: {subtype}.",
        context_signature=context,
        opportunity_count=opportunities,
        occurrence_rate=rate,
        trend_direction=trend,
        is_strength=is_strength,
        detector_id="event_context",
        detector_version=1,
        evidence={"impact_score": impact},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class TestAssembly:
    def test_absence_is_stated_for_a_new_player(self, db, user):
        block = assemble_event_context(db, user.id, fen=AFTER_E4)
        assert "Nothing on record" in block
        assert "new for the player" in block

    def test_relevant_patterns_are_included_with_rate_and_trend(self, db, user):
        add_pattern(
            db,
            user.id,
            subtype="endgame_technique_failure__endgame|level|simplified|triggered",
            context="endgame|level|simplified|triggered",
            impact=0.9,
            rate=0.35,
            trend="persistent",
        )
        block = assemble_event_context(db, user.id, fen="8/8/4k3/8/8/4K3/4P3/8 w - - 0 1")
        assert "## Recurring patterns" in block
        assert "35% of 40 similar decisions" in block
        assert "persistent" in block
        assert "pattern_id=" in block

    def test_relevance_ranks_same_phase_and_impact_first(self, db, user):
        add_pattern(
            db,
            user.id,
            subtype="opening_thing__opening|level|complex|self_initiated",
            context="opening|level|complex|self_initiated",
            impact=0.4,
        )
        add_pattern(
            db,
            user.id,
            subtype="endgame_thing__endgame|level|simplified|triggered",
            context="endgame|level|simplified|triggered",
            impact=0.8,
        )
        endgame_fen = "8/8/4k3/8/8/4K3/4P3/8 w - - 0 1"
        block = assemble_event_context(db, user.id, fen=endgame_fen, phase="endgame")
        # The endgame pattern must appear before the opening one.
        assert block.index("endgame_thing") < block.index("opening_thing")

    def test_at_most_the_pattern_budget_is_included(self, db, user):
        for index in range(MAX_PATTERNS + 3):
            add_pattern(
                db,
                user.id,
                subtype=f"pattern_{index}__endgame|level|simplified|triggered",
                context="endgame|level|simplified|triggered",
                impact=0.5 + index * 0.01,
            )
        block = assemble_event_context(db, user.id, fen="8/8/4k3/8/8/4K3/4P3/8 w - - 0 1")
        assert block.count("pattern_id=") <= MAX_PATTERNS

    def test_budget_drops_whole_blocks_and_stays_within_the_cap(self, db, user):
        for index in range(MAX_PATTERNS):
            add_pattern(
                db,
                user.id,
                # Long and distinct: (user_id, type, subtype) is unique, and the
                # point is to overflow the character budget.
                subtype=("x" * 150) + f"_{index}__endgame|level|simplified|triggered",
                context="endgame|level|simplified|triggered",
                impact=0.9,
            )
        block = assemble_event_context(db, user.id, fen="8/8/4k3/8/8/4K3/4P3/8 w - - 0 1")
        assert len(block) <= MAX_BLOCK_CHARS
        assert "## Recurring patterns" in block

    def test_patterns_without_rate_still_render(self, db, user):
        row = add_pattern(
            db,
            user.id,
            subtype="phase_weakness__x",
            context="endgame|level|simplified|triggered",
            impact=0.5,
        )
        row.occurrence_rate = None
        row.opportunity_count = None
        db.commit()
        block = assemble_event_context(db, user.id, fen="8/8/4k3/8/8/4K3/4P3/8 w - - 0 1")
        assert "12 times" in block

    def test_missing_fen_returns_nothing(self, db, user):
        assert assemble_event_context(db, user.id, fen=None) == ""

    def test_unparseable_fen_is_handled(self, db, user):
        assert assemble_event_context(db, user.id, fen="not-a-fen") == ""

    def test_strengths_are_deprioritised(self, db, user):
        add_pattern(
            db,
            user.id,
            subtype="strength__endgame|level|simplified|triggered",
            context="endgame|level|simplified|triggered",
            impact=0.9,
            is_strength=True,
        )
        add_pattern(
            db,
            user.id,
            subtype="weakness__endgame|level|simplified|triggered",
            context="endgame|level|simplified|triggered",
            impact=0.85,
        )
        block = assemble_event_context(db, user.id, fen="8/8/4k3/8/8/4K3/4P3/8 w - - 0 1")
        assert block.index("weakness__") < block.index("strength__")


class TestGroundingRule:
    """The admissibility rule must survive on every return path.

    A live context-quality run failed the no-history probe because the rule was
    added to the budgeted path only and the absence path kept a hand-typed copy
    of the message. Both branches are asserted here, and the absence text is
    required to be the shared constant rather than a re-typed string.
    """

    def test_present_when_history_exists(self, db, user):
        add_pattern(
            db,
            user.id,
            subtype="weakness__endgame|level|simplified|triggered",
            context="endgame|level|simplified|triggered",
            impact=0.7,
        )
        block = assemble_event_context(db, user.id, fen="8/8/4k3/8/8/4K3/4P3/8 w - - 0 1")
        assert GROUNDING_RULE in block

    def test_present_when_no_history(self, db, user):
        assert GROUNDING_RULE in absence_context()

    def test_absence_path_uses_the_shared_constant(self, db, user):
        """Asking for an unknown position returns exactly the shared string."""
        block = assemble_event_context(db, user.id, fen="8/8/4k3/8/8/4K3/4P3/8 w - - 0 1")
        assert block == absence_context()
