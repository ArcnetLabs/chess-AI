"""Coach-summary composer guards (style, length, fallback behaviour)."""

import pytest

from app.services.profiles import summary_composer
from app.services.profiles.summary_composer import (
    MAX_SENTENCES,
    _clean,
    build_coach_summary,
    phase_findings,
    style_violation,
)


class TestPhaseFindings:
    def test_ranks_phases_from_the_scores(self):
        strongest, weakest = phase_findings({"opening": 58, "middlegame": 39, "endgame": 23})
        assert strongest == "opening"
        assert weakest == "endgame"

    def test_needs_two_phases(self):
        assert phase_findings({"opening": 58}) == (None, None)
        assert phase_findings(None) == (None, None)


class TestStyleViolation:
    @pytest.mark.parametrize(
        "text",
        [
            "Your average ACPL in this phase is high.",
            "You sit below the threshold in the opening.",
            "That pattern carries critical severity.",
            "Your phase score improved.",
            "Accuracy percentage is climbing.",
            "You score 57% in the opening.",
        ],
    )
    def test_flags_jargon(self, text):
        assert style_violation(text) is not None

    def test_accepts_plain_coaching_copy(self):
        clean = (
            "Your openings are solid, but you give away material once the middlegame "
            "gets sharp. Slowing down before you commit to a plan is the fastest gain."
        )
        assert style_violation(clean) is None


class TestClean:
    def test_caps_sentence_count(self):
        five = "One here. Two here. Three here. Four here. Five here."
        cleaned = _clean(five)
        assert cleaned.count(". ") + 1 <= MAX_SENTENCES
        assert cleaned.endswith(".")

    def test_caps_length_on_a_sentence_boundary(self):
        long_text = " ".join(
            f"This is sentence number {index} and it runs on for a while." for index in range(20)
        )
        cleaned = _clean(long_text)
        assert len(cleaned) <= summary_composer.MAX_SUMMARY_CHARS
        assert cleaned.endswith(".")

    def test_short_text_is_untouched(self):
        assert _clean("  Short and clean.  ") == "Short and clean."


class TestBuildCoachSummaryFallback:
    def test_uses_fallback_without_a_provider(self, monkeypatch):
        monkeypatch.setattr(summary_composer, "_provider_configured", lambda: False)
        summary = build_coach_summary(
            fallback="Deterministic text.",
            archetype="Strong Opening / Weak Endgame",
            games_analyzed_count=200,
            patterns_detected_count=9,
        )
        assert summary == "Deterministic text."

    def test_uses_fallback_when_the_llm_raises(self, monkeypatch):
        monkeypatch.setattr(summary_composer, "_provider_configured", lambda: True)

        def boom(**kwargs):  # pragma: no cover - exercised via build_coach_summary
            raise RuntimeError("provider down")

        monkeypatch.setattr(summary_composer, "asyncio", type("X", (), {"run": staticmethod(boom)}))
        summary = build_coach_summary(
            fallback="Deterministic text.",
            archetype=None,
            games_analyzed_count=10,
            patterns_detected_count=1,
        )
        assert summary == "Deterministic text."
