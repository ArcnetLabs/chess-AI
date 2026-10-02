"""The coach must not be handed internal vocabulary, and must be told not to use it.

Two failure modes, both observed in production:

* a reply told a player about their "blunder rate" — a phrase that came from a pattern
  description *I* wrote into the model's context ("High blunder rate: averages 1.5
  blunders per game (threshold 1.5)"), so the model was echoing my text rather than
  inventing the term;
* model-facing context labelled engine numbers with their internal names ("ACPL",
  "phase ACPL", "severity="), which is where that vocabulary comes from in the first
  place.

So this checks both directions: what the coach is *sent*, and what it is *told*. The
word list is the reply scorer's own list, so the rule and the scoring cannot disagree
about what counts as engine jargon.
"""

from pathlib import Path

from app.services.chat.chess_coach import COACH_ANSWER_INSTRUCTIONS
from app.services.evaluation.model_eval import BANNED_COACH_TERMS

SERVICES = Path(__file__).resolve().parents[1] / "app" / "services"

# The exact phrasings that were reaching the model, by file. Each one was removed
# because it named an internal measure inside text the coach is given.
REMOVED_PHRASINGS = {
    "patterns/blunder_cluster_detector.py": ("High blunder rate", "blunders per game"),
    "patterns/phase_weakness_detector.py": ("ACPL averages", "threshold {"),
    "patterns/opening_weakness_detector.py": ("opening ACPL averages", "threshold {"),
    "chat/chess_coach.py": ("ACPL {", "phase ACPL:"),
    "chat/context_assembler.py": ("severity={",),
}


class TestModelFacingTextUsesCoachVoice:
    def test_the_removed_phrasings_stay_removed(self):
        """A regression guard on exactly what was fixed, file by file.

        Source-level rather than rendered: these strings are interpolated into pattern
        descriptions while they are built, so the surest cheap check is that the
        phrasing is gone from the module that produced it.
        """
        for relative, phrases in REMOVED_PHRASINGS.items():
            source = (SERVICES / relative).read_text(encoding="utf-8")
            # Comments may quote the old wording as history; generated text may not.
            code_lines = [
                line
                for line in source.splitlines()
                if not line.lstrip().startswith("#")
            ]
            code = "\n".join(code_lines)
            for phrase in phrases:
                assert phrase not in code, f"{relative} still emits {phrase!r}"

    def test_the_reply_scorer_and_this_file_agree_on_the_words(self):
        for term in ("acpl", "centipawn", "blunder rate", "threshold", "severity"):
            assert term in BANNED_COACH_TERMS, term


class TestTheCoachIsToldTheVocabularyRule:
    def test_the_instruction_names_the_banned_terms(self):
        for term in ("ACPL", "centipawn", "blunder rate", "threshold", "severity"):
            assert term in COACH_ANSWER_INSTRUCTIONS, f"not told about {term!r}"

    def test_it_says_what_to_do_instead(self):
        assert "Describe the chess instead" in COACH_ANSWER_INSTRUCTIONS

    def test_it_forbids_asking_for_facts_the_coach_was_already_given(self):
        """A live reply asked the player to share a rating the app had on record."""
        assert "Never ask the player for something the facts above already give you" in (
            COACH_ANSWER_INSTRUCTIONS
        )
        assert "say plainly which figure you lack" in COACH_ANSWER_INSTRUCTIONS

    def test_the_rule_travels_into_the_evaluation_prompt(self):
        """The harness must measure the rule as well as production sending it."""
        from app.services.evaluation.coach_probes import coaching_system_prompt

        assert "blunder rate" in coaching_system_prompt("anything")
        assert "Never ask the player for something the facts above" in (
            coaching_system_prompt("anything")
        )


class TestThePlayerNumbersBlockUsesCoachVoice:
    """The accuracy and rating evidence is new model-facing text, so it is held to
    the same word list as everything else the coach is sent."""

    def _context_with_numbers(self, db) -> str:
        from app.models.game import Game, GameAnalysis
        from app.models.user import User
        from app.services.chat.context_assembler import assemble_coach_context

        user = User(
            email="coach-vocabulary@example.com",
            supabase_user_id="coach-vocabulary-sub",
            connection_type="username_only",
            current_ratings={
                "chess_rapid": {"last": {"rating": 1420}},
                "chess_blitz": {"last": {"rating": 1310}},
            },
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        game = Game(
            user_id=user.id,
            chesscom_game_id="coach-vocabulary-game",
            is_analyzed=True,
        )
        db.add(game)
        db.flush()
        db.add(
            GameAnalysis(
                game_id=game.id,
                user_color="white",
                user_acpl=30.0,
                accuracy_percentage=72.0,
            )
        )
        db.commit()
        return assemble_coach_context(db, user.id)

    def test_the_numbers_block_contains_no_engine_vocabulary(self, db):
        context = self._context_with_numbers(db)

        assert "## Player Numbers" in context
        lowered = context.lower()
        assert [term for term in BANNED_COACH_TERMS if term in lowered] == []

    def test_the_numbers_block_is_jargon_free_by_the_context_quality_gate(self, db):
        from app.services.evaluation.context_quality import verify_context_quality

        context = self._context_with_numbers(db)
        checks = verify_context_quality(context, expect_history=True)

        assert checks.checks["no_engine_jargon"] is True
        assert [v for v in checks.violations if "vocabulary" in v] == []
