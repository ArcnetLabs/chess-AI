"""Behavioural hypotheses: how this player's decisions tend to go wrong.

The distinction that matters: a **pattern** says *what* recurs ("endgame technique
failures in level, non-simplified positions"), while a hypothesis says *when it
tends to happen* — the condition under which the player's error rate departs from
their own baseline. Both are measured from the same decision series, so a hypothesis
is a comparison rather than a new detector.

Three rules, because this is the layer where an AI coach is most tempted to
speculate:

1. **About decisions in positions, never about the person.** "Errors cluster right
   after an opponent creates a threat" is checkable against stored rows. "You are
   impatient" is not, and never appears here.
2. **Compared to the player's own baseline**, not to other players or to an
   absolute standard — the only comparison the data supports.
3. **Silence is a valid answer.** A dimension with too few decisions in either
   group, or a gap too small to matter, produces no hypothesis at all rather than a
   weak one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from loguru import logger

from app.services.patterns.event_pattern_detector import Decision

# Both sides of the comparison need this many decisions before anything is claimed.
MIN_HYPOTHESIS_OPPORTUNITIES = 20
# The group rate must be at least this multiple of the baseline before the
# difference is worth calling a tendency.
MIN_RATE_RATIO = 1.5
# ...and at least this far above it in absolute terms, so a 1% baseline cannot
# produce a "tendency" from a 2% rate.
MIN_RATE_GAP = 0.05

HYPOTHESIS_TRIGGER = "trigger_sensitivity"
HYPOTHESIS_PHASE = "phase_tendency"
HYPOTHESIS_COMPLEXITY = "complexity_tendency"
HYPOTHESIS_MATERIAL = "material_tendency"


@dataclass(eq=False)
class _GroupRates:
    label: str
    occurrences: int
    opportunities: int
    rate: float


def _rate(decisions: Sequence[Decision]) -> Optional[float]:
    if not decisions:
        return None
    errors = sum(1 for d in decisions if d.event_types)
    return round(errors / len(decisions), 4)


def _group(label: str, decisions: Sequence[Decision]) -> _GroupRates:
    errors = sum(1 for d in decisions if d.event_types)
    return _GroupRates(
        label=label,
        occurrences=errors,
        opportunities=len(decisions),
        rate=round(errors / len(decisions), 4) if decisions else 0.0,
    )


def _confidence(group: _GroupRates, baseline: _GroupRates) -> float:
    """How much weight the claim deserves, from sample size and size of the gap.

    Deliberately a product of two capped factors rather than a made-up score: more
    decisions and a bigger departure from the player's own baseline both raise it,
    and neither alone can carry a hypothesis to full confidence.
    """
    sample = min(1.0, group.opportunities / (2 * MIN_HYPOTHESIS_OPPORTUNITIES))
    gap = 0.0
    if baseline.rate > 0:
        gap = min(1.0, (group.rate / baseline.rate) / (2 * MIN_RATE_RATIO))
    return round(max(0.0, min(1.0, sample * gap)), 3)


def _hypothesis(
    *,
    kind: str,
    statement: str,
    group: _GroupRates,
    baseline: _GroupRates,
    dimension: Dict,
    pattern_ids: Optional[List[int]] = None,
) -> Optional[Dict]:
    """Build a hypothesis, or refuse to when the evidence does not support one."""
    if (
        group.opportunities < MIN_HYPOTHESIS_OPPORTUNITIES
        or baseline.opportunities < MIN_HYPOTHESIS_OPPORTUNITIES
    ):
        return None
    if baseline.rate <= 0:
        return None
    ratio = group.rate / baseline.rate
    if ratio < MIN_RATE_RATIO or (group.rate - baseline.rate) < MIN_RATE_GAP:
        return None

    return {
        "kind": kind,
        "statement": statement,
        "group": {
            "label": group.label,
            "occurrences": group.occurrences,
            "opportunities": group.opportunities,
            "rate": group.rate,
        },
        "baseline": {
            "label": baseline.label,
            "occurrences": baseline.occurrences,
            "opportunities": baseline.opportunities,
            "rate": baseline.rate,
        },
        "rate_ratio": round(ratio, 3),
        "confidence": _confidence(group, baseline),
        "dimension": dimension,
        "thresholds": {
            "min_opportunities": MIN_HYPOTHESIS_OPPORTUNITIES,
            "min_rate_ratio": MIN_RATE_RATIO,
            "min_rate_gap": MIN_RATE_GAP,
        },
        "pattern_ids": list(pattern_ids or []),
    }


def _trigger_split(decisions: Sequence[Decision]) -> tuple[List[Decision], List[Decision]]:
    triggered = [d for d in decisions if (d.context or "").endswith("|triggered")]
    self_initiated = [d for d in decisions if (d.context or "").endswith("|self-initiated")]
    return triggered, self_initiated


def _complexity_split(decisions: Sequence[Decision]) -> tuple[List[Decision], List[Decision]]:
    busy = [d for d in decisions if "|complex|" in (d.context or "")]
    simple = [d for d in decisions if "|simplified|" in (d.context or "")]
    return busy, simple


def _material_split(decisions: Sequence[Decision]) -> tuple[List[Decision], List[Decision]]:
    ahead = [
        d
        for d in decisions
        if (d.context or "").startswith(("opening|ahead", "middlegame|ahead", "endgame|ahead"))
    ]
    rest = [d for d in decisions if d not in ahead]
    return ahead, rest


def _phase_split(decisions: Sequence[Decision]) -> List[tuple[str, List[Decision]]]:
    by_phase: Dict[str, List[Decision]] = {}
    for decision in decisions:
        if not decision.phase:
            continue
        by_phase.setdefault(decision.phase, []).append(decision)
    return list(by_phase.items())


def _contexts_of(decisions: Sequence[Decision]) -> set[str]:
    return {d.context for d in decisions if d.context}


def _patterns_by_context(patterns: Sequence[object]) -> Dict[str, List[int]]:
    """Map each situation signature to the patterns detected in it."""
    mapping: Dict[str, List[int]] = {}
    for pattern in patterns or ():
        context = getattr(pattern, "context_signature", None)
        pattern_id = getattr(pattern, "id", None)
        if context and pattern_id is not None:
            mapping.setdefault(context, []).append(int(pattern_id))
    return mapping


def _supporting_patterns(
    decisions: Sequence[Decision], by_context: Dict[str, List[int]]
) -> List[int]:
    """Pattern ids that fired in exactly the situations this hypothesis covers.

    This is the link that makes a hypothesis auditable: every claim points at the
    patterns detected in its own group, so it can be walked back to occurrences,
    moves and engine evaluations. A pattern detected elsewhere is never attached.
    """
    ids: set[int] = set()
    for context in _contexts_of(decisions):
        ids.update(by_context.get(context, ()))
    return sorted(ids)


def build_behavioural_hypotheses(
    decisions: Sequence[Decision],
    patterns: Sequence[object] = (),
) -> List[Dict]:
    """Measured tendencies, most confident first. Deterministic and LLM-free.

    ``patterns`` supplies the supporting ids: a hypothesis is attached only to
    patterns detected in the situations it covers, so every claim can be walked back
    through occurrences to moves and engine evaluations.
    """
    if not decisions:
        return []

    by_context = _patterns_by_context(patterns)
    overall = _group("all your decisions", decisions)
    hypotheses: List[Dict] = []

    # 1. Does the opponent's move change the error rate?
    triggered, self_initiated = _trigger_split(decisions)
    if triggered and self_initiated:
        group, baseline = _group("right after an opponent's threat", triggered), _group(
            "when you are left to your own plans", self_initiated
        )
        result = _hypothesis(
            kind=HYPOTHESIS_TRIGGER,
            statement=(
                f"Errors cluster in the move after an opponent creates a threat: "
                f"{round(group.rate * 100)}% of those decisions versus "
                f"{round(baseline.rate * 100)}% when you are left to your own plans."
            ),
            group=group,
            baseline=baseline,
            dimension={"name": "opponent trigger"},
            pattern_ids=_supporting_patterns(triggered, by_context),
        )
        if result:
            hypotheses.append(result)

    # 2. Busy positions versus simplified ones.
    busy, simple = _complexity_split(decisions)
    if busy and simple:
        group, baseline = _group("in busy positions", busy), _group("in simplified positions", simple)
        result = _hypothesis(
            kind=HYPOTHESIS_COMPLEXITY,
            statement=(
                f"Busy positions are where it goes wrong: {round(group.rate * 100)}% of "
                f"decisions there versus {round(baseline.rate * 100)}% in simplified ones."
            ),
            group=group,
            baseline=baseline,
            dimension={"name": "position complexity"},
            pattern_ids=_supporting_patterns(busy, by_context),
        )
        if result:
            hypotheses.append(result)

    # 3. Ahead versus the rest — the conversion question.
    ahead, rest = _material_split(decisions)
    if ahead and rest:
        group, baseline = _group("when you are ahead", ahead), _group(
            "when you are not ahead", rest
        )
        result = _hypothesis(
            kind=HYPOTHESIS_MATERIAL,
            statement=(
                f"More goes wrong when you are ahead: {round(group.rate * 100)}% of those "
                f"decisions versus {round(baseline.rate * 100)}% otherwise."
            ),
            group=group,
            baseline=baseline,
            dimension={"name": "material state"},
        )
        if result:
            hypotheses.append(result)

    # 4. Which phase carries the damage, against the player's own overall rate.
    for phase, phase_decisions in _phase_split(decisions):
        group = _group(f"in the {phase}", phase_decisions)
        result = _hypothesis(
            kind=HYPOTHESIS_PHASE,
            statement=(
                f"Most of the damage happens in the {phase}: "
                f"{round(group.rate * 100)}% of your {phase} decisions versus "
                f"{round(overall.rate * 100)}% across the game."
            ),
            group=group,
            baseline=overall,
            dimension={"name": "game phase", "phase": phase},
            pattern_ids=_supporting_patterns(phase_decisions, by_context),
        )
        if result:
            hypotheses.append(result)

    hypotheses.sort(key=lambda item: (-item["confidence"], item["kind"]))
    logger.debug(f"behavioural hypotheses: {len(hypotheses)} from {len(decisions)} decisions")
    return hypotheses
