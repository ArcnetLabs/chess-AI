"""Grounding evaluation for coach context assembly (P3-CM-05)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.services.chat.context_assembler import assemble_coach_context

_EVAL_DATA_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "coach_grounding_eval.json"
)


@dataclass(frozen=True)
class GroundingExpectation:
    """Expected facts that assembled coach context should contain."""

    pattern_subtypes: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    require_profile: bool = False


@dataclass(frozen=True)
class GroundingEvalCase:
    """Single grounding evaluation question with expected citations."""

    id: str
    question: str
    expected: GroundingExpectation


@dataclass
class GroundingCaseResult:
    """Per-case grounding score."""

    case_id: str
    question: str
    passed: bool


@dataclass
class GroundingEvalResult:
    """Aggregate grounding evaluation outcome."""

    pass_count: int
    total: int
    pass_rate: float
    case_results: list[GroundingCaseResult] = field(default_factory=list)


def _parse_expectation(raw: dict) -> GroundingExpectation:
    return GroundingExpectation(
        pattern_subtypes=tuple(raw.get("pattern_subtypes") or ()),
        keywords=tuple(raw.get("keywords") or ()),
        require_profile=bool(raw.get("require_profile", False)),
    )


def load_grounding_eval_set(path: Path | None = None) -> list[GroundingEvalCase]:
    """Load the canonical grounding eval dataset from JSON."""
    data_path = path or _EVAL_DATA_PATH
    with data_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    cases: list[GroundingEvalCase] = []
    for entry in payload:
        cases.append(
            GroundingEvalCase(
                id=str(entry["id"]),
                question=str(entry["question"]),
                expected=_parse_expectation(entry.get("expected") or {}),
            )
        )
    return cases


def score_context_grounding(context: str, expected: GroundingExpectation) -> bool:
    """
    Return True when assembled context includes all required grounding facts.

    Uses case-insensitive substring matching on the full context block (v1).
    """
    ctx = context.lower()

    if expected.require_profile:
        if "insufficient analyzed games" in ctx:
            return False
        if "profile_version:" not in ctx:
            return False

    for subtype in expected.pattern_subtypes:
        if subtype.lower() not in ctx:
            return False

    for keyword in expected.keywords:
        if keyword.lower() not in ctx:
            return False

    return True


def evaluate_coach_context(
    db: Session,
    user_id: int,
    cases: list[GroundingEvalCase],
    *,
    top_patterns: int = 5,
) -> GroundingEvalResult:
    """
    Assemble coach context per case and score grounding against expectations.

    Does not invoke the LLM — evaluates context assembly only.
    """
    case_results: list[GroundingCaseResult] = []
    pass_count = 0

    for case in cases:
        context = assemble_coach_context(
            db,
            user_id,
            top_patterns=top_patterns,
            query_text=case.question,
        )
        passed = score_context_grounding(context, case.expected)
        if passed:
            pass_count += 1
        case_results.append(
            GroundingCaseResult(
                case_id=case.id,
                question=case.question,
                passed=passed,
            )
        )

    total = len(cases)
    pass_rate = (pass_count / total) if total else 0.0
    return GroundingEvalResult(
        pass_count=pass_count,
        total=total,
        pass_rate=pass_rate,
        case_results=case_results,
    )
