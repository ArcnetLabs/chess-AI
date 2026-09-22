"""
Coach-voice profile summary.

The profile page headline should read like a coach talking to the player, not
like an engine report: the first deterministic version produced sentences such
as "Opening-phase ACPL averages 125.9 across 36 games (threshold 30.0)", which
is jargon and also collides with the headline's own game count.

`build_coach_summary` asks the configured coach LLM for 2-3 plain-language
sentences grounded strictly in the supplied aggregates, and returns the
deterministic phrasing when no provider is configured or the call fails, so the
profile always carries a usable summary.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from loguru import logger

MAX_SUMMARY_CHARS = 460

_SYSTEM_PROMPT = (
    "You are a chess coach writing a short profile summary for one of your students. "
    "Write 2 to 3 complete sentences in second person ('you'), plain everyday language, "
    "at most 55 words in total. "
    "Say what they do well and the single most important thing to fix. "
    "Style to match: \"Your openings are solid, but you give away material once the "
    "middlegame gets sharp. Slowing down before you commit to a plan is the fastest "
    "rating gain available to you.\" "
    "The strongest and weakest phases are given to you — never contradict them, and "
    "never call a phase both a strength and a weakness. "
    "You may mention how many games were analyzed. Do not quote any other number and "
    "never use engine jargon or metric names (no phase scores, percentages, ratings, "
    "blunder counts, ACPL, thresholds, severity labels, or raw detector wording). "
    "Never invent facts beyond the data provided. "
    "No preamble, no headings, no lists, no quotes — just the summary sentences, and "
    "always finish every sentence you start."
)


def _provider_configured() -> bool:
    """True when a coach LLM provider is configured (never true in tests)."""
    try:
        from ...core.config import settings  # local import keeps import cycles out
    except Exception:  # pragma: no cover - config always importable in app
        return False

    return bool(
        getattr(settings, "LLM_LOCAL_API_KEY", "")
        or getattr(settings, "OPENROUTER_API_KEY", "")
        or getattr(settings, "OPENAI_API_KEY", "")
    )


def phase_findings(
    phase_performance: Optional[Dict[str, Any]],
) -> tuple[Optional[str], Optional[str]]:
    """
    Strongest and weakest phase from the phase scores.

    This is the same source the archetype label uses, so the summary's
    strength/weakness claims cannot contradict the archetype. The detector's own
    weakness wording is derived from ACPL thresholds and can name a different
    phase; it stays available to the coach as detail but is not restated as the
    headline finding.
    """
    entries = [
        (str(phase), float(score))
        for phase, score in (phase_performance or {}).items()
        if isinstance(score, (int, float))
    ]
    if len(entries) < 2:
        return None, None
    entries.sort(key=lambda item: item[1])
    weakest, strongest = entries[0][0], entries[-1][0]
    return strongest, weakest


def _facts(
    *,
    archetype: Optional[str],
    games_analyzed_count: int,
    patterns_detected_count: int,
    primary_strengths: Optional[List[str]],
    primary_weaknesses: Optional[List[str]],
    phase_performance: Optional[Dict[str, Any]],
    tactical_themes: Optional[Dict[str, Any]],
    style_indicators: Optional[Dict[str, Any]],
    rating_trends: Optional[Dict[str, Any]],
) -> str:
    """Compact, factual briefing for the LLM — numbers it may reference."""
    themes = tactical_themes or {}
    style = style_indicators or {}
    ratings = ((rating_trends or {}).get("current") or {})
    rating_bits = []
    for label, key in (("rapid", "chess_rapid"), ("blitz", "chess_blitz"), ("bullet", "chess_bullet")):
        value = (ratings.get(key) or {}).get("last", {}).get("rating")
        if isinstance(value, (int, float)) and value:
            rating_bits.append(f"{label} {int(value)}")

    strongest, weakest = phase_findings(phase_performance)
    lines = [
        f"games analyzed: {games_analyzed_count}",
        f"recurring patterns detected: {patterns_detected_count}",
        f"profile archetype label (internal, do not quote verbatim): {archetype or 'unknown'}",
    ]
    if strongest and weakest:
        lines.append(
            f"strongest phase: {strongest}; weakest phase: {weakest} "
            "(state these consistently — do not call either one both)"
        )
    lines.append(
        f"move quality totals across those games: "
        f"{int(themes.get('blunders') or 0)} blunders, "
        f"{int(themes.get('mistakes') or 0)} mistakes, "
        f"{int(themes.get('inaccuracies') or 0)} inaccuracies"
    )
    if rating_bits:
        lines.append("current ratings: " + ", ".join(rating_bits))
    if style:
        lines.append(f"style indicators (0-1): {style}")
    if primary_strengths:
        lines.append("detector notes — strengths (internal wording): " + " | ".join(primary_strengths[:2]))
    if primary_weaknesses:
        lines.append(
            "detector notes — weaknesses (internal wording, secondary detail): "
            + " | ".join(primary_weaknesses[:3])
        )
    return "\n".join(lines)


def _clean(text: str) -> str:
    """
    One paragraph, no wrapping quotes, capped for the card layout.

    The cap trims on a sentence boundary: a previous version cut mid-clause and
    shipped "...spending some structured study time on." to the profile headline.
    """
    cleaned = " ".join(text.strip().strip('"').strip().split())
    if len(cleaned) <= MAX_SUMMARY_CHARS:
        return cleaned

    window = cleaned[:MAX_SUMMARY_CHARS]
    boundary = window.rfind(". ")
    if boundary >= 80:
        return window[: boundary + 1].strip()
    # No complete sentence fits — finish the phrase we keep rather than cutting
    # a word in half.
    words = window.rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{words}."


# Metric names and symbols the summary must never carry: the whole point of this
# composer is that the profile headline reads as coaching, not as an engine
# report. The prompt asks for this, and a model can still slip — one live run
# produced "...as evidenced by your average ACPL score in this phase" — so the
# output is checked rather than trusted.
_BANNED_TERMS = (
    "acpl",
    "centipawn",
    "threshold",
    "severity",
    "phase score",
    "accuracy percentage",
    "evaluation score",
)


def style_violation(text: str) -> Optional[str]:
    """The banned term or symbol the text carries, if any."""
    low = text.lower()
    for term in _BANNED_TERMS:
        if term in low:
            return term
    if "%" in text:
        return "percent sign"
    return None


def build_coach_summary(
    *,
    fallback: str,
    archetype: Optional[str],
    games_analyzed_count: int,
    patterns_detected_count: int,
    primary_strengths: Optional[List[str]] = None,
    primary_weaknesses: Optional[List[str]] = None,
    phase_performance: Optional[Dict[str, Any]] = None,
    tactical_themes: Optional[Dict[str, Any]] = None,
    style_indicators: Optional[Dict[str, Any]] = None,
    rating_trends: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Coach-voice summary, or ``fallback`` when no LLM is available.

    Synchronous by design: it runs inside the Celery profile-build task, which
    is not an async context.
    """
    if not _provider_configured():
        logger.info("Coach summary: no LLM provider configured, using deterministic text")
        return fallback

    facts = _facts(
        archetype=archetype,
        games_analyzed_count=games_analyzed_count,
        patterns_detected_count=patterns_detected_count,
        primary_strengths=primary_strengths,
        primary_weaknesses=primary_weaknesses,
        phase_performance=phase_performance,
        tactical_themes=tactical_themes,
        style_indicators=style_indicators,
        rating_trends=rating_trends,
    )

    async def _call(correction: Optional[str] = None) -> str:
        from ..integration.ai_client import AIClient

        client = AIClient()
        user_content = "Player data:\n" f"{facts}\n\n" "Write the summary now."
        if correction:
            user_content += (
                f"\n\nYour previous attempt used the forbidden term '{correction}'. "
                "Rewrite it without any metric names, scores or percentages."
            )
        result = await client.chat_completion(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.4,
            max_tokens=220,
        )
        return str(result.get("content") or "")

    for attempt in (1, 2):
        try:
            text = asyncio.run(_call(None if attempt == 1 else violation))
        except Exception as exc:  # noqa: BLE001 — the profile must still build
            logger.warning(f"Coach summary LLM failed, using deterministic text: {exc}")
            return fallback

        cleaned = _clean(text)
        violation = style_violation(cleaned)
        if len(cleaned) < 40:
            logger.warning("Coach summary LLM returned too little text; using deterministic text")
            return fallback
        if violation is None:
            logger.info(f"Coach summary generated via LLM ({len(cleaned)} chars)")
            return cleaned
        logger.warning(f"Coach summary used banned term '{violation}' (attempt {attempt})")

    logger.warning("Coach summary kept leaking jargon; using deterministic text")
    return fallback
