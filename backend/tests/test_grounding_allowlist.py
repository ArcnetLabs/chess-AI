"""The grounding check must measure what it claims to measure.

The check's message was "context cites game 1420 that is not in its evidence", reported
against a *reply* that had cited a game from its own context. Two defects behind one
sentence:

* the parameter was named ``context`` while reply scoring passed a reply into it, so the
  report pointed at the context builder rather than at this function;
* ``Probe.allowed_game_ids`` was never populated, so "not in its evidence" meant "no game
  may be named at all" — a reply doing the right thing by citing the player's own games
  was scored as ungrounded.

Both directions are pinned here: a citation the context supports passes, and an invented
one still fails, because relaxing the first must not cost the second.
"""

from app.services.evaluation.coach_eval import verify_grounding
from app.services.evaluation.coach_probes import (
    games_cited_in,
    pattern_ids_cited_in,
)

CONTEXT = (
    "## Similar positions from your own games\n"
    "- Game 1420 move 12: you played Nf3\n"
    "- Game 87 move 30: you played h4\n"
    "## Your games in this kind of position\n"
    "- Game 1461 on 2026-09-20 against kubasuivan, win — 19 comparable positions\n"
    "## Recurring patterns\n- endgame technique (pattern_id=119)\n"
)


class TestTheAllowListComesFromTheContext:
    def test_games_are_read_out_of_the_context(self):
        assert games_cited_in(CONTEXT) == (87, 1420, 1461)

    def test_pattern_ids_are_read_out_of_the_context(self):
        assert pattern_ids_cited_in(CONTEXT) == (119,)

    def test_a_context_without_games_yields_nothing(self):
        assert games_cited_in("Nothing on record for this position yet.") == ()


class TestGroundingNowMeasuresWhatItClaims:
    def test_citing_a_game_the_context_gave_is_grounded(self):
        """The case that was reported as a failure against a correct reply."""
        reply = "Your record here mirrors Game 1420, where the same thing happened."
        assert (
            verify_grounding(
                reply,
                allowed_game_ids=games_cited_in(CONTEXT),
                allowed_pattern_ids=pattern_ids_cited_in(CONTEXT),
            )
            == []
        )

    def test_inventing_a_game_still_fails(self):
        reply = "This happened in Game 999999 as well."
        violations = verify_grounding(
            reply,
            allowed_game_ids=games_cited_in(CONTEXT),
            allowed_pattern_ids=pattern_ids_cited_in(CONTEXT),
        )
        assert violations and "999999" in violations[0]

    def test_inventing_a_pattern_still_fails(self):
        reply = "This is your pattern_id=424242."
        violations = verify_grounding(
            reply,
            allowed_game_ids=games_cited_in(CONTEXT),
            allowed_pattern_ids=pattern_ids_cited_in(CONTEXT),
        )
        assert violations and "424242" in violations[0]

    def test_the_message_no_longer_blames_the_context(self):
        violations = verify_grounding(
            "Game 999999 again", allowed_game_ids=[], allowed_pattern_ids=[]
        )
        assert "not in the evidence it was given" in violations[0]
        assert not violations[0].startswith("context cites")
