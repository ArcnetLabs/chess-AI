"""Context-quality checks: the preconditions the model-side decision depends on.

The phase 8 decision (train or not) rests on the model failing *despite* correct
context. That has two halves, and only one of them needs credentials:

1. **Is the context correct and safe to coach from?** Verifiable now, offline.
2. **What does the model do with it?** Needs a provider (see ``model_eval``).

This module measures the first half, plus the deterministic coaching text the
product falls back to when no provider is available — which is user-visible text
and therefore deserves the same rules as model output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from app.services.evaluation.model_eval import BANNED_COACH_TERMS


@dataclass
class ContextChecks:
    """Deterministic checks on a context block."""

    name: str
    checks: Dict[str, bool] = field(default_factory=dict)
    violations: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(self.checks.values())


def verify_context_quality(
    context: str,
    *,
    name: str = "context",
    expect_history: bool,
    requires_grounding_rule: bool = True,
) -> ContextChecks:
    """Check a context block against the rules the coach depends on.

    * the grounding rule must be present, or the model has no instruction not to
      invent chess truth;
    * no engine vocabulary, because this text is read by a player;
    * when history is expected, evidence ids must be present (a context that says
      "recurring pattern" without an id cannot be cited or audited);
    * when history is absent, the absence must be stated explicitly rather than
      left for the model to infer.
    """
    result = ContextChecks(name=name)
    lowered = context.lower()

    if requires_grounding_rule:
        grounded = "do not invent" in lowered or "never" in lowered
        result.checks["grounding_rule_present"] = grounded
        if not grounded:
            result.violations.append("context does not tell the model not to invent chess truth")

    jargon = [term for term in BANNED_COACH_TERMS if term in lowered]
    # "thresholds" appear inside stored evidence payloads, which are never shown
    # to the model; only the rendered context is checked here.
    result.checks["no_engine_jargon"] = not jargon
    if jargon:
        result.violations.append(f"engine vocabulary in model-facing context: {jargon}")

    if expect_history:
        has_ids = "pattern_id=" in context or "game " in lowered
        result.checks["citable_evidence"] = has_ids
        if not has_ids:
            result.violations.append("history expected but no citable pattern or game id present")
        result.checks["absence_stated"] = True
    else:
        stated = "nothing on record" in lowered or "new for the player" in lowered
        result.checks["absence_stated"] = stated
        if not stated:
            result.violations.append("no history, but the context does not say so")
        result.checks["citable_evidence"] = True

    return result


def summarise_context_checks(results: Sequence[ContextChecks]) -> Dict:
    """Aggregate context-quality scores."""
    total_checks = sum(len(r.checks) for r in results)
    passed_checks = sum(sum(1 for ok in r.checks.values() if ok) for r in results)
    return {
        "contexts": len(results),
        "contexts_passed": sum(1 for r in results if r.passed),
        "checks_passed": passed_checks,
        "checks_total": total_checks,
        "violations": [v for r in results for v in r.violations],
    }
