"""Tests for practice focus: ChessRun prescribes, the partners are where you practise.

The properties that matter, and why each is here:

* a focus is recommended with its evidence, so the player is told *why*;
* a partner is named only when the fix genuinely belongs there;
* nothing invents drill content or links on a partner platform we have no
  integration with — that would be exactly the ungrounded claim the rest of the
  system refuses to make;
* recommending is recorded in the coaching ledger, because "have I taught you
  this, and did it work?" is only answerable if the offer is a stored fact;
* the coach's prompt carries the same rule, so the model does not undo it.
"""

from unittest.mock import patch

import pytest

from app.models.coaching_intervention import CoachingIntervention
from app.models.pattern import PlayerPattern
from app.services.coaching.interventions import (
    INTERVENTION_PRACTICE,
    SOURCE_SYSTEM,
)
from app.services.coaching.practice_focus import (
    PRACTICE_BY_EVENT,
    PRACTICE_PARTNERS,
    PARTNER_CHESSFLOW,
    PARTNER_CHESSREPS,
    build_practice_focus,
    offer_practice_focus,
)


@pytest.fixture
def user(db):
    from app.models.user import User

    row = User(
        supabase_user_id="practice-focus-user",
        email="practice@chessrun.local",
        chesscom_username="practice_tester",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def pattern(
    db,
    user,
    *,
    subtype: str,
    occurrences: int = 29,
    opportunities: int = 79,
    rate: float = 0.367,
    is_strength: bool = False,
) -> PlayerPattern:
    row = PlayerPattern(
        user_id=user.id,
        pattern_type="decision_pattern",
        pattern_subtype=subtype,
        context_signature=subtype.split("__", 1)[1] if "__" in subtype else None,
        severity="critical",
        confidence_score=0.99,
        occurrence_count=occurrences,
        affected_games_count=18,
        affected_games_ratio=0.5,
        pattern_description="Recurring pattern: an endgame technique error.",
        occurrence_rate=rate,
        opportunity_count=opportunities,
        is_strength=is_strength,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class TestFocusBuilding:
    def test_focus_carries_its_evidence(self, db, user):
        pattern(db, user, subtype="endgame_technique_failure__endgame|level|complex|triggered")
        item = build_practice_focus(db, user.id)[0]

        assert item["focus"] == "your endgame technique"
        assert "37%" in item["why"]
        assert "79" in item["why"]

    def test_recurring_beats_rare(self, db, user):
        pattern(
            db,
            user,
            subtype="pawn_structure_error__middlegame|level|complex|self-initiated",
            occurrences=3,
            opportunities=400,
            rate=0.008,
        )
        pattern(
            db,
            user,
            subtype="tactical_miss__middlegame|level|complex|self-initiated",
            occurrences=20,
            opportunities=60,
            rate=0.333,
        )
        items = build_practice_focus(db, user.id)
        assert items[0]["focus"] == "spotting tactics when they appear"

    def test_strengths_are_not_practice_focus(self, db, user):
        pattern(db, user, subtype="solid_endgame", is_strength=True)
        assert build_practice_focus(db, user.id) == []

    def test_legacy_patterns_are_skipped_not_guessed(self, db, user):
        """An aggregate pattern names no event, so any focus would be a guess."""
        pattern(db, user, subtype="endgame_major_swings")
        assert build_practice_focus(db, user.id) == []

    def test_limit_is_respected(self, db, user):
        for index, subtype in enumerate(
            [
                "tactical_miss__a|level|complex|self-initiated",
                "endgame_technique_failure__b|level|complex|triggered",
                "opening_deviation__c|level|complex|self-initiated",
            ]
        ):
            pattern(db, user, subtype=subtype, occurrences=30 - index)
        assert len(build_practice_focus(db, user.id, limit=2)) == 2


class TestPartnerRouting:
    def test_openings_go_to_chessreps(self, db, user):
        pattern(db, user, subtype="opening_deviation__opening|level|complex|self-initiated")
        assert build_practice_focus(db, user.id)[0]["partner"]["key"] == PARTNER_CHESSREPS

    def test_calculation_goes_to_chessflow(self, db, user):
        pattern(db, user, subtype="major_blunder__middlegame|level|complex|self-initiated")
        assert build_practice_focus(db, user.id)[0]["partner"]["key"] == PARTNER_CHESSFLOW

    def test_no_destination_when_neither_fits(self, db, user):
        """Better no call to action than sending the player somewhere irrelevant."""
        pattern(db, user, subtype="exchange_error__middlegame|level|complex|self-initiated")
        assert build_practice_focus(db, user.id)[0]["partner"] is None

    def test_partners_are_honest_about_not_being_integrated(self):
        for partner in PRACTICE_PARTNERS.values():
            assert partner.status == "coming_soon"
            assert partner.url is None

    def test_every_routed_event_is_a_real_event_type(self):
        """The routing table must cover the vocabulary the detector emits.

        A typo here would silently drop a whole class of weakness from practice
        focus, which is the kind of failure no test would otherwise notice.
        """
        from app.services.patterns import event_pattern_detector as detector

        labels = set(detector._EVENT_LABELS)
        unknown = set(PRACTICE_BY_EVENT) - labels
        assert not unknown, f"practice routing names events that do not exist: {unknown}"

    def test_routed_events_all_name_a_focus(self):
        """Every routed event must produce player-facing wording.

        (Note for whoever reads this next: ``CONCEPT_DRILLS`` in the detector is
        *not* keyed by event type and almost always falls back to "calculation",
        so it cannot validate this table — which is part of why practice routing
        lives here instead.)
        """
        for event_type, (focus, partner) in PRACTICE_BY_EVENT.items():
            assert focus and focus == focus.lower(), event_type
            assert partner is None or partner in PRACTICE_PARTNERS, event_type


class TestLedgerRecording:
    def test_offering_records_a_practice_recommendation(self, db, user):
        row = pattern(db, user, subtype="tactical_miss__middlegame|level|complex|self-initiated")
        offer_practice_focus(db, user.id)

        recorded = db.query(CoachingIntervention).one()
        assert recorded.intervention_type == INTERVENTION_PRACTICE
        assert recorded.source == SOURCE_SYSTEM
        assert recorded.pattern_id == row.id
        assert recorded.payload["partner"] == PARTNER_CHESSFLOW
        # The descriptive fields travel, so the outcome stays measurable even if
        # the pattern row is later pruned.
        assert recorded.pattern_subtype == row.pattern_subtype
        assert recorded.context_signature == row.context_signature

    def test_offering_twice_does_not_duplicate(self, db, user):
        pattern(db, user, subtype="tactical_miss__middlegame|level|complex|self-initiated")
        offer_practice_focus(db, user.id)
        offer_practice_focus(db, user.id)
        assert db.query(CoachingIntervention).count() == 1

    def test_nothing_is_recorded_when_there_is_no_focus(self, db, user):
        assert offer_practice_focus(db, user.id) == []
        assert db.query(CoachingIntervention).count() == 0


class TestCoachPromptRule:
    def test_rule_forbids_inventing_partner_content(self):
        from app.services.chat.chess_coach import PRACTICE_HANDOFF_RULE

        assert "ChessReps" in PRACTICE_HANDOFF_RULE
        assert "ChessFlow" in PRACTICE_HANDOFF_RULE
        assert "never name a specific drill" in PRACTICE_HANDOFF_RULE
        assert "suggest the player practises inside ChessRun" in PRACTICE_HANDOFF_RULE

    @pytest.mark.asyncio
    async def test_rule_reaches_the_real_prompt(self):
        from app.services.chat import ChatContext
        from app.services.chat.chess_coach import ChessCoach, PRACTICE_HANDOFF_RULE

        class _CapturingAIClient:
            def __init__(self):
                self.captured = None

            async def chat_completion(self, messages, temperature, max_tokens):
                self.captured = messages
                return {"content": "ok"}

        ai_client = _CapturingAIClient()
        coach = ChessCoach(ai_client=ai_client)
        await coach._llm_coach_reply(
            "What should I work on?", ChatContext(session_id="s1"), "Grounding facts block"
        )

        system_content = ai_client.captured[0]["content"]
        assert "Where to practise" in system_content
        assert PRACTICE_HANDOFF_RULE.strip() in system_content
