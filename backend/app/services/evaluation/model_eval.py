"""Model-side evaluation: does the coach use the context it is given?

Phase 7 measured the intelligence layers (events, patterns, retrieval, context)
and found them correct and grounded. This measures the *prose layer* — the part
that decides whether fine-tuning is justified at all. The architecture doc set
that condition in advance: train only if the model fails **despite receiving
correct context**, so the comparison here is deliberately:

* **context_only** — the player evidence, with no coaching instruction;
* **prompt_plus_context** — the same evidence with the coach's system prompt.

Scoring is deterministic and runs before any judge, because fluent prose is not
evidence of correct reasoning (see the phase 1 audit and the research notes).
Checks, each pass/fail:

1. **Grounding** — no game id or pattern id outside the evidence supplied.
2. **No invented evaluations** — no engine number the context never contained.
3. **No engine vocabulary** — the product rule: players read chess ideas, not
   centipawns.
4. **Personalisation** — when history was supplied, the reply must actually use
   it; swapping the history must change the answer.
5. **Honest uncertainty** — with no matching history, the reply must say so
   rather than implying memory it does not have.

The provider is pluggable and optional: with no credentials the harness still
assembles and reports the exact prompts it would send, so the gap is visible
rather than silent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from loguru import logger
from sqlalchemy.orm import Session

from app.services.evaluation.coach_eval import (
    verify_grounding,
    verify_no_invented_evaluations,
)

# A coach in ChessRun's voice never speaks engine dialect at a player.
BANNED_COACH_TERMS = (
    "acpl",
    "centipawn",
    "cp loss",
    "eval bar",
    "evaluation bar",
    "threshold",
    "severity",
    "blunder rate",
)

# Signals that a reply is engaging with the player's own history.
HISTORY_SIGNALS = (
    "you played",
    "you've played",
    "you have played",
    "your games",
    "your own games",
    "in game ",
    "before",
    "again",
    "recurring",
    "pattern",
)

# Signals that a reply is honestly saying "this is new".
UNCERTAINTY_SIGNALS = (
    "new",
    "first time",
    "haven't seen",
    "have not seen",
    "no history",
    "nothing on record",
    "unknown",
    "don't have",
    "do not have",
)

# A reply claiming a pattern when none was supplied is the failure this catches.
PATTERN_CLAIM = re.compile(r"\b(recurring|pattern|you (always|often|keep))\b", re.I)

Provider = Callable[[str, str], str]


@dataclass
class Probe:
    """One question with the context a correct system should supply."""

    name: str
    question: str
    context: str
    expects_history: bool
    expects_uncertainty: bool = False
    allowed_game_ids: Sequence[int] = field(default_factory=tuple)
    allowed_pattern_ids: Sequence[int] = field(default_factory=tuple)
    notes: str = ""


@dataclass
class ProbeResult:
    name: str
    reply: Optional[str]
    checks: Dict[str, bool] = field(default_factory=dict)
    violations: List[str] = field(default_factory=list)
    skipped: Optional[str] = None

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(self.checks.values())


def score_reply(probe: Probe, reply: str) -> ProbeResult:
    """Deterministic scoring of one reply. No model is used to judge."""
    result = ProbeResult(name=probe.name, reply=reply)
    lowered = reply.lower()

    grounding = verify_grounding(
        reply,
        allowed_game_ids=probe.allowed_game_ids,
        allowed_pattern_ids=probe.allowed_pattern_ids,
    )
    result.checks["grounding"] = not grounding
    result.violations.extend(grounding)

    invented = verify_no_invented_evaluations(reply, probe.context)
    result.checks["no_invented_evaluations"] = not invented
    result.violations.extend(invented)

    jargon = [term for term in BANNED_COACH_TERMS if term in lowered]
    result.checks["no_engine_jargon"] = not jargon
    if jargon:
        result.violations.append(f"engine vocabulary in reply: {jargon}")

    if probe.expects_history:
        used = any(signal in lowered for signal in HISTORY_SIGNALS)
        result.checks["uses_player_history"] = used
        if not used:
            result.violations.append("history was supplied but the reply ignores it")
    else:
        result.checks["uses_player_history"] = True

    if probe.expects_uncertainty:
        honest = any(signal in lowered for signal in UNCERTAINTY_SIGNALS)
        # Claiming a pattern with no evidence is the specific failure.
        claimed = bool(PATTERN_CLAIM.search(reply))
        result.checks["honest_uncertainty"] = honest and not claimed
        if claimed:
            result.violations.append("claimed a pattern although no history was supplied")
        elif not honest:
            result.violations.append("no history was supplied but the reply did not say so")
    else:
        result.checks["honest_uncertainty"] = True

    return result


def run_probes(
    db: Session,
    probes: Sequence[Probe],
    *,
    provider: Optional[Provider] = None,
    system_prompt: str = "",
) -> Dict:
    """Run every probe, scoring replies when a provider is available.

    Without a provider the report still contains each assembled context and the
    exact prompt that would be sent, so an unmeasured model is visible rather than
    assumed to be fine.
    """
    results: List[ProbeResult] = []
    prompts: List[Dict] = []

    for probe in probes:
        if provider is None:
            results.append(
                ProbeResult(
                    name=probe.name,
                    reply=None,
                    skipped="no LLM provider configured",
                )
            )
            prompts.append(
                {
                    "name": probe.name,
                    "question": probe.question,
                    "context_chars": len(probe.context),
                    "expects_history": probe.expects_history,
                    "context_preview": probe.context[:400],
                }
            )
            continue
        try:
            reply = provider(system_prompt, f"{probe.context}\n\nQuestion: {probe.question}")
        except Exception as exc:  # noqa: BLE001 - a provider fault is data, not a crash
            logger.error(f"probe {probe.name} provider failed: {exc}")
            results.append(
                ProbeResult(name=probe.name, reply=None, skipped=f"provider failed: {exc}")
            )
            continue
        results.append(score_reply(probe, reply))

    scored = [r for r in results if r.reply is not None]
    report = {
        "provider": "configured" if provider is not None else "unavailable",
        "probes": len(results),
        "scored": len(scored),
        "passed": sum(1 for r in scored if r.passed),
        "checks": {},
        "results": [
            {
                "name": r.name,
                "passed": r.passed,
                "skipped": r.skipped,
                "checks": r.checks,
                "violations": r.violations,
            }
            for r in results
        ],
    }
    if scored:
        for check in scored[0].checks:
            report["checks"][check] = sum(1 for r in scored if r.checks.get(check))
    if prompts:
        report["prompts"] = prompts
    return report
