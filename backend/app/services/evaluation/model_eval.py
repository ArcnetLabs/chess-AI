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
from typing import Callable, Dict, List, Optional, Sequence, Union

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

# What this check is for: a reply asserting the player has a history when none was
# supplied. Two heuristics were tried and both produced false positives on *correct*
# replies, which is why the third matches the assertion rather than the vocabulary:
#
#   1. matching the word "pattern" — the absence context itself contains "patterns", and
#      the right answer denies having one ("I don't have a pattern on record for this");
#   2. matching "recurring" — the right answer may look forward ("once you play more
#      games, we'll be able to spot recurring issues"), which claims nothing about the
#      past. That sentence was reported as a model failure against a reply whose other
#      sentence was "there's nothing on record".
#
# Fabricated specifics remain the business of the id-based grounding check; this one
# covers prose claims, and treats forward-looking or conditional framing as not a claim.
_PATTERN_ASSERTION = re.compile(
    r"("
    r"you (always|often|keep|kept|usually|tend to|have a habit)"
    r"|this (recurs|keeps (happening|coming back))"
    r"|you'?ve (done|made|played) this"
    r"|a (recurring|repeated|consistent) (problem|issue|mistake|weakness|pattern)"
    r")",
    re.I,
)

# Framing that makes a mention forward-looking or conditional rather than a claim.
_NON_CLAIM_FRAMING = (
    "once you",
    "we'll",
    "we will",
    "will be able",
    "if you",
    "as you play",
    "may ",
    "might ",
    "would ",
    "could ",
)

# A sentence containing any of these is denying or declining to claim, not asserting.
_DENIAL_MARKERS = (
    "no ",
    "not ",
    "nothing",
    "don't",
    "do not",
    "doesn't",
    "does not",
    "haven't",
    "have not",
    "hasn't",
    "has not",
    "isn't",
    "aren't",
    "without",
    "never",
    "yet",
)


def _pattern_claim(reply: str) -> Optional[str]:
    """The sentence asserting the player has a recurring problem, or ``None``.

    Returns the offending sentence rather than a boolean so the violation can quote its
    evidence: a check that says "claimed a pattern" without showing the sentence cannot
    be audited by whoever reads the report — and this one was wrong twice, invisibly.
    """
    for sentence in re.split(r"(?<=[.!?])\s+", reply):
        if not _PATTERN_ASSERTION.search(sentence):
            continue
        lowered = sentence.lower()
        if any(marker in lowered for marker in _DENIAL_MARKERS):
            continue
        if any(marker in lowered for marker in _NON_CLAIM_FRAMING):
            continue
        return sentence.strip()
    return None

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
        # Claiming a pattern with no evidence is the specific failure — judged on the
        # claim, not on the vocabulary, and reported with the sentence that made it.
        claim = _pattern_claim(reply)
        result.checks["honest_uncertainty"] = honest and claim is None
        if claim is not None:
            result.violations.append(f"claimed a pattern although none was supplied: {claim!r}")
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
    system_prompt: Union[str, Callable[[Probe], str]] = "",
) -> Dict:
    """Run every probe, scoring replies when a provider is available.

    ``system_prompt`` may be a callable, which is how the harness sends the *real*
    coaching instructions: they echo the question, so they differ per probe. A single
    fixed string is still accepted for tests and simple arms.

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
            prompt_for_probe = (
                system_prompt(probe) if callable(system_prompt) else system_prompt
            )
            reply = provider(
                prompt_for_probe, f"{probe.context}\n\nQuestion: {probe.question}"
            )
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
                # The reply itself, so a failure can be audited from the report instead
                # of being taken on trust. A check that only says "claimed a pattern"
                # cannot be argued with — and this one was wrong for a whole round
                # because nothing in the report showed what the model actually wrote.
                "reply_excerpt": (r.reply or "")[:600],
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
