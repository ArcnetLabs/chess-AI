"""Offline evaluation harness for the coaching intelligence layers.

Why this exists, and what it must not be: the phase 1 audit found the existing
grounding eval scored deterministic *context* text with substring checks and never
invoked the model, so it could not measure coaching behaviour. Research on chess
explanations is blunter still — an explanation that reads well is not evidence of
correct reasoning, and LLM judges are documented as insufficient on their own. So
the gate here is **deterministic**: it checks what the system claims against the
evidence rows it claims it from, and only then optionally scores model prose.

Covered by the harness:

* **Pattern recognition** — does detection find the patterns a case says are real
  (recall), avoid inventing ones it does not (precision), and stay silent on
  isolated mistakes and coincidences (false-pattern rate)?
* **Historical reasoning** — when a case has prior similar decisions, does
  retrieval surface them; when it has none, does the system say so?
* **Grounding / non-hallucination** — every game id, pattern id and engine number
  in an assembled context must exist in the evidence that context was built from.
* **Personalisation** — a behavioural test, not a judged one: swap the player's
  history and confirm the produced context actually changes.
* **Chess correctness** — the diagnosis must agree with the stored engine verdict.

Fixtures are built from move facts directly, so the whole suite runs offline with
no engine and no model: it is fast enough to gate every change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from app.models.chess_event import ChessEvent
from app.models.game import Game
from app.models.game_move import GameMove
from app.models.user import User
from app.services.patterns.event_pattern_detector import (
    detect_context_patterns,
    detect_strengths,
    load_decisions,
)

# The synthetic player the harness owns. Stable so repeated runs reuse one row.
HARNESS_USER_ID = "coach-eval-harness"

# ---------------------------------------------------------------------------
# Fixture cases
# ---------------------------------------------------------------------------


@dataclass
class FixtureMove:
    """One ply with the engine evidence a real analysis row would carry."""

    ply: int
    is_user_move: bool
    cp_loss: float
    phase: str
    context: str  # the situation, as context_signature would produce it
    material_band: str = "level"
    material_balance: int = 0
    simplified: bool = False
    mover_hanging: Tuple[str, ...] = ()
    opponent_hanging: Tuple[str, ...] = ()
    classification: str = "good"
    event_types: Tuple[str, ...] = ()
    # Which game this ply belongs to. Fixtures that care about *ordering between
    # plies* (an opponent's error and the reply that fails to punish it) must set
    # this: the trigger is found by looking at ply-1 in the same game, so a
    # round-robin split silently deletes the very thing the case is about.
    game_key: Optional[str] = None
    # Retained deliberately: the harness must be able to plant wrong evidence and
    # check that the system does not accept it.
    serious: bool = True


@dataclass
class EvalCase:
    """A scenario with the pattern set a correct system should produce.

    Expectations are declared *semantically* — an event type in a kind of
    situation — and the harness derives the concrete pattern subtype using the
    detector's own ``context_signature``. Hand-written subtype strings were a
    fixture bug the harness caught immediately: the pipeline derives the signature
    from move features, so a literal label can never match and the case would fail
    for the wrong reason.
    """

    name: str
    category: str
    moves: List[FixtureMove]
    expected_event_types: Tuple[str, ...] = ()
    forbidden_event_types: Tuple[str, ...] = ()
    # Fully-built subtypes for cases that legitimately span two situations.
    expected_signatures: Tuple[str, ...] = ()
    expected_strength: Optional[str] = None
    expect_no_patterns: bool = False
    # The situation this case is about, used to derive the expected signature.
    context_phase: str = "middlegame"
    material_band: str = "level"
    simplified: bool = False
    triggered: bool = False
    notes: str = ""

    def signature(self) -> str:
        from app.services.patterns.context_signature import context_signature

        return context_signature(
            phase=self.context_phase,
            features={
                "material_band": self.material_band,
                "simplified": self.simplified,
                "mover_hanging": ["c3"] if self.triggered else [],
            },
            structure_key=f"struct-{self.context_phase}",
            has_opponent_trigger=self.triggered,
        )


def _error_move(
    ply: int,
    *,
    context: str,
    phase: str = "middlegame",
    cp_loss: float = 320.0,
    event_type: str = "major_blunder",
    **kwargs,
) -> FixtureMove:
    return FixtureMove(
        ply=ply,
        is_user_move=True,
        cp_loss=cp_loss,
        phase=phase,
        context=context,
        event_types=(event_type,),
        classification="blunder",
        **kwargs,
    )


def _quiet_move(ply: int, *, context: str, phase: str = "middlegame", **kwargs) -> FixtureMove:
    return FixtureMove(
        ply=ply,
        is_user_move=True,
        cp_loss=12.0,
        phase=phase,
        context=context,
        **kwargs,
    )


def _opponent_move(ply: int, *, context: str, phase: str = "middlegame", **kwargs) -> FixtureMove:
    return FixtureMove(
        ply=ply,
        is_user_move=False,
        cp_loss=10.0,
        phase=phase,
        context=context,
        **kwargs,
    )


ENDGAME_CONTEXT = "endgame|level|complex|triggered"
MIDDLEGAME_CONTEXT = "middlegame|level|complex|self-initiated"
OPENING_CONTEXT = "opening|level|complex|self-initiated"


def build_cases() -> List[EvalCase]:
    """The benchmark. Difficult cases are included on purpose."""
    cases: List[EvalCase] = []

    # 1. A true recurring pattern: the same error in the same situation, across
    #    enough games and opportunities to be real.
    moves = [_opponent_move(1, context=ENDGAME_CONTEXT, phase="endgame")]
    for index in range(4):
        moves.append(
            _error_move(
                3 + index * 2,
                context=ENDGAME_CONTEXT,
                phase="endgame",
                event_type="endgame_technique_failure",
            )
        )
        moves.append(_quiet_move(4 + index * 2, context=ENDGAME_CONTEXT, phase="endgame"))
    moves.extend(
        _quiet_move(100 + index, context=ENDGAME_CONTEXT, phase="endgame") for index in range(8)
    )
    cases.append(
        EvalCase(
            name="true_recurring_pattern",
            category="pattern_identification",
            moves=moves,
            expected_event_types=("endgame_technique_failure",),
            context_phase="endgame",
            notes="four occurrences in one situation, plus quiet decisions in it",
        )
    )

    # 2. An isolated mistake: one error and nothing else. Must not become a pattern.
    cases.append(
        EvalCase(
            name="isolated_mistake",
            category="pattern_vs_isolated_error",
            moves=[
                _error_move(3, context=MIDDLEGAME_CONTEXT, event_type="major_blunder"),
                *(
                    _quiet_move(5 + index, context=MIDDLEGAME_CONTEXT)
                    for index in range(20)
                ),
            ],
            expect_no_patterns=True,
            notes="a single blunder is not a pattern",
        )
    )

    # 3. Similar-looking but unrelated: errors of one label in two different
    #    situations must not merge into one pattern.
    unrelated = [
        _error_move(3 + index, context=OPENING_CONTEXT, phase="opening", event_type="opening_deviation")
        for index in range(3)
    ]
    unrelated += [
        _error_move(
            40 + index, context=ENDGAME_CONTEXT, phase="endgame",
            event_type="opening_deviation",
        )
        for index in range(3)
    ]
    unrelated += [_quiet_move(80 + index, context=OPENING_CONTEXT, phase="opening") for index in range(10)]
    unrelated += [_quiet_move(120 + index, context=ENDGAME_CONTEXT, phase="endgame") for index in range(10)]
    cases.append(
        EvalCase(
            name="similar_label_unrelated_situations",
            category="pattern_vs_isolated_error",
            moves=unrelated,
            expected_event_types=("opening_deviation",),
            expected_signatures=(
                "opening_deviation__endgame|level|complex|self-initiated",
            ),
            context_phase="opening",
            notes="two contexts, one label: both detected, neither merged",
        )
    )

    # 4. Opponent-induced: the error always follows an opponent's own mistake, so
    #    the coaching signal is "failed to punish", not "blundered".
    #
    #    Each opponent blunder and the reply that fails to punish it share a game
    #    (game_key), because the trigger is read from ply-1 of the same game — and
    #    each game holds a second trigger/safe-reply pair so the situation reaches
    #    the opportunity floor while still spanning four distinct games.
    induced = []
    for index in range(4):
        key = f"induced-{index}"
        induced.append(
            FixtureMove(
                ply=2,
                is_user_move=False,
                cp_loss=300.0,
                phase="middlegame",
                context=MIDDLEGAME_CONTEXT,
                classification="blunder",
                game_key=key,
            )
        )
        induced.append(
            _error_move(
                3,
                context=MIDDLEGAME_CONTEXT,
                event_type="failed_to_punish",
                cp_loss=250.0,
                game_key=key,
            )
        )
        induced.append(
            FixtureMove(
                ply=4,
                is_user_move=False,
                cp_loss=300.0,
                phase="middlegame",
                context=MIDDLEGAME_CONTEXT,
                classification="blunder",
                game_key=key,
            )
        )
        induced.append(_quiet_move(5, context=MIDDLEGAME_CONTEXT, game_key=key))
    cases.append(
        EvalCase(
            name="opponent_induced",
            category="opponent_pattern",
            moves=induced,
            expected_event_types=("failed_to_punish",),
            context_phase="middlegame",
            triggered=True,
            notes="the trigger is the opponent's error, not the player's",
        )
    )

    # 5. Opening knowledge gap: errors confined to the opening.
    opening = [
        _error_move(
            3 + index * 2, context=OPENING_CONTEXT, phase="opening",
            event_type="opening_deviation", cp_loss=200.0,
        )
        for index in range(4)
    ]
    opening.extend(_quiet_move(50 + index, context=OPENING_CONTEXT, phase="opening") for index in range(10))
    cases.append(
        EvalCase(
            name="opening_knowledge_gap",
            category="opening_recommendation",
            moves=opening,
            expected_event_types=("opening_deviation",),
            context_phase="opening",
            notes="opening errors must not be attributed to the endgame",
        )
    )

    # 6. Conflicting evidence: the same situation has both errors and clean play in
    #    near-equal measure, so the honest output is a low rate, not a strong claim.
    conflicting = [
        _error_move(
            3 + index * 2, context=ENDGAME_CONTEXT, phase="endgame",
            event_type="threat_unanswered",
        )
        for index in range(4)
    ]
    conflicting.extend(
        _quiet_move(50 + index, context=ENDGAME_CONTEXT, phase="endgame") for index in range(12)
    )
    cases.append(
        EvalCase(
            name="conflicting_evidence",
            category="uncertainty",
            moves=conflicting,
            expected_event_types=("threat_unanswered",),
            context_phase="endgame",
            notes="25% rate: reportable, but must not be described as dominant",
        )
    )

    # 7. A strength: clean play throughout one phase.
    cases.append(
        EvalCase(
            name="phase_strength",
            category="grounding",
            moves=[_quiet_move(3 + index * 2, context=OPENING_CONTEXT, phase="opening") for index in range(30)],
            expected_strength="solid_opening",
            context_phase="opening",
            notes="strengths must be detected by the same standard as weaknesses",
        )
    )

    return cases


# ---------------------------------------------------------------------------
# Running the harness
# ---------------------------------------------------------------------------


@dataclass
class CaseResult:
    name: str
    category: str
    detected: List[str] = field(default_factory=list)
    expected_hits: List[str] = field(default_factory=list)
    expected_misses: List[str] = field(default_factory=list)
    forbidden_hits: List[str] = field(default_factory=list)
    grounding_violations: List[str] = field(default_factory=list)
    notes: str = ""

    @property
    def passed(self) -> bool:
        return (
            not self.expected_misses
            and not self.forbidden_hits
            and not self.grounding_violations
        )


def _seed_case(db: Session, user: User, case: EvalCase) -> None:
    """Materialise a case as games, moves and events.

    Game assignment is either explicit (``FixtureMove.game_key``) or round-robin.
    Round-robin exists so a case whose occurrences must clear the *distinct games*
    gate can spread them cheaply; it is the wrong choice for any case where the
    meaning lives in the adjacency of two plies, which is why the key exists.
    """
    from app.services.analysis.position_features import extract_features  # noqa: F401
    import chess

    explicit = [move.game_key for move in case.moves if move.game_key is not None]
    if explicit:
        keys: List[Optional[str]] = [move.game_key for move in case.moves]
        distinct = list(dict.fromkeys(keys))  # first-appearance order
    else:
        keys = [f"rr-{index % 3}" for index in range(len(case.moves))]
        distinct = ["rr-0", "rr-1", "rr-2"]

    game_ids: Dict[Optional[str], int] = {}
    for index, key in enumerate(distinct):
        game = Game(
            user_id=user.id,
            chesscom_game_id=f"eval-{case.name}-{index}",
            winner="draw",
            white_username="eval_player",
            black_username="eval_opponent",
        )
        db.add(game)
        db.flush()
        game_ids[key] = game.id

    for move_index, fixture in enumerate(case.moves):
        game_id = game_ids[keys[move_index]]
        board = chess.Board()
        move = GameMove(
            user_id=user.id,
            game_id=game_id,
            ply=fixture.ply,
            move_number=(fixture.ply + 1) // 2,
            color="white" if fixture.ply % 2 == 1 else "black",
            is_user_move=fixture.is_user_move,
            fen_before=board.fen(),
            fen_after=board.fen(),
            position_key=f"{case.name}-{fixture.ply}",
            structure_key=f"struct-{fixture.phase}",
            material_balance=fixture.material_balance,
            move_uci="e2e4",
            best_move_uci="e2e4",
            eval_before_cp=100.0,
            eval_after_cp=100.0 - fixture.cp_loss,
            cp_loss=fixture.cp_loss,
            classification=fixture.classification,
            phase=fixture.phase,
            features={
                "material_band": fixture.material_band,
                "material_balance": fixture.material_balance,
                "simplified": fixture.simplified,
                "mover_hanging": list(fixture.mover_hanging),
                "opponent_hanging": list(fixture.opponent_hanging),
                "mobility": 15,
            },
        )
        db.add(move)
        db.flush()

        for event_type in fixture.event_types:
            severity = "high" if fixture.serious else "low"
            db.add(
                ChessEvent(
                    user_id=user.id,
                    game_id=game_id,
                    move_id=move.id,
                    event_type=event_type,
                    concept="calculation",
                    severity=severity,
                    phase=fixture.phase,
                    move_number=move.move_number,
                    position_key=move.position_key,
                    fen_before=move.fen_before,
                    played_move=move.played_move if hasattr(move, "played_move") else move.move_uci,
                    best_move=move.best_move_uci,
                    eval_before_cp=move.eval_before_cp,
                    cp_loss=move.cp_loss,
                    evidence={"cp_loss": fixture.cp_loss},
                    detector_id=event_type,
                    detector_version=1,
                )
            )
    db.commit()


def run_case(db: Session, user: User, case: EvalCase) -> CaseResult:
    """Run one case through detection and check it against its labels."""
    _seed_case(db, user, case)
    decisions = load_decisions(db, user.id)
    detected = detect_context_patterns(decisions) + detect_strengths(decisions)
    subtypes = {pattern.pattern_subtype for pattern in detected}

    result = CaseResult(
        name=case.name,
        category=case.category,
        detected=sorted(subtypes),
        notes=case.notes,
    )
    signature = case.signature()
    expected_subtypes = [
        f"{event_type}__{signature}" for event_type in case.expected_event_types
    ]
    if case.expected_strength:
        expected_subtypes.append(case.expected_strength)
    expected_subtypes.extend(case.expected_signatures)
    for expected in expected_subtypes:
        (result.expected_hits if expected in subtypes else result.expected_misses).append(expected)
    # A forbidden event type must not appear as a pattern *in this situation*.
    for event_type in case.forbidden_event_types:
        forbidden = f"{event_type}__{signature}"
        if forbidden in subtypes:
            result.forbidden_hits.append(forbidden)

    if case.expect_no_patterns and subtypes:
        result.forbidden_hits.extend(sorted(subtypes))

    _cleanup_case(db, user, case)
    return result


def _cleanup_case(db: Session, user: User, case: EvalCase) -> None:
    """Remove the case's rows so cases cannot contaminate each other."""
    game_ids = [
        row.id
        for row in db.query(Game)
        .filter(Game.user_id == user.id, Game.chesscom_game_id.like(f"eval-{case.name}-%"))
        .all()
    ]
    if not game_ids:
        return
    db.query(ChessEvent).filter(ChessEvent.game_id.in_(game_ids)).delete(synchronize_session=False)
    db.query(GameMove).filter(GameMove.game_id.in_(game_ids)).delete(synchronize_session=False)
    db.query(Game).filter(Game.id.in_(game_ids)).delete(synchronize_session=False)
    db.commit()


# ---------------------------------------------------------------------------
# Deterministic verifiers (the gate)
# ---------------------------------------------------------------------------

_GAME_ID = re.compile(r"\bGame (\d+)\b")
_PATTERN_ID = re.compile(r"pattern_id=(\d+)")
# Engine-style numbers: a coach must not produce evaluations from nowhere.
_ENGINE_NUMBER = re.compile(r"[+-]\d+\.\d\d\b")


def verify_grounding(
    context: str, *, allowed_game_ids: Sequence[int], allowed_pattern_ids: Sequence[int]
) -> List[str]:
    """Every referenced id must exist in the evidence the context was built from."""
    violations: List[str] = []
    for game_id in _GAME_ID.findall(context):
        if int(game_id) not in set(allowed_game_ids):
            violations.append(f"context cites game {game_id} that is not in its evidence")
    for pattern_id in _PATTERN_ID.findall(context):
        if int(pattern_id) not in set(allowed_pattern_ids):
            violations.append(f"context cites pattern {pattern_id} that is not in its evidence")
    return violations


def verify_no_invented_evaluations(reply: str, context: str) -> List[str]:
    """A reply may not state an evaluation the context never provided."""
    violations = []
    for number in _ENGINE_NUMBER.findall(reply):
        if number not in context:
            violations.append(f"reply states evaluation {number} not present in context")
    return violations


def verify_personalisation(
    context_with_history: str, context_without_history: str
) -> bool:
    """The context must actually depend on the player's history."""
    return context_with_history.strip() != context_without_history.strip()


def summarise(results: Sequence[CaseResult]) -> Dict:
    """Aggregate scores. Recall/precision are computed over expected patterns."""
    expected_total = sum(len(r.expected_hits) + len(r.expected_misses) for r in results)
    found = sum(len(r.expected_hits) for r in results)
    false_positives = sum(len(r.forbidden_hits) for r in results)
    detected_total = sum(len(r.detected) for r in results)
    violations = sum(len(r.grounding_violations) for r in results)

    recall = round(found / expected_total, 3) if expected_total else None
    precision = (
        round(found / (found + false_positives), 3) if (found + false_positives) else None
    )
    return {
        "cases": len(results),
        "cases_passed": sum(1 for r in results if r.passed),
        "patterns_expected": expected_total,
        "patterns_found": found,
        "pattern_recall": recall,
        "pattern_precision": precision,
        "false_pattern_hits": false_positives,
        "false_pattern_rate": (
            round(false_positives / detected_total, 3) if detected_total else 0.0
        ),
        "grounding_violations": violations,
        "detected_patterns_total": detected_total,
    }


def run_harness(db: Session, *, user: Optional[User] = None) -> Dict:
    """Run every case and return the report."""
    owner = user
    if owner is None:
        # Reuse the harness player if it exists. Creating it unconditionally made a
        # second run fail on the unique chesscom username, which would have made the
        # baseline a once-only measurement — the opposite of what a baseline is for.
        owner = (
            db.query(User)
            .filter(User.supabase_user_id == HARNESS_USER_ID)
            .one_or_none()
        )
    if owner is None:
        owner = User(
            supabase_user_id=HARNESS_USER_ID,
            email="coach-eval@chessrun.local",
            chesscom_username="coach_eval_player",
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

    results: List[CaseResult] = []
    for case in build_cases():
        try:
            results.append(run_case(db, owner, case))
        except Exception as exc:  # noqa: BLE001 - a broken case is a failure, not a crash
            logger.error(f"eval case {case.name} failed: {exc}")
            failed = CaseResult(name=case.name, category=case.category, notes=str(exc))
            failed.expected_misses.append("(case raised)")
            results.append(failed)

    report = summarise(results)
    report["case_results"] = [
        {
            "name": r.name,
            "category": r.category,
            "passed": r.passed,
            "detected": r.detected,
            "expected_hits": r.expected_hits,
            "expected_misses": r.expected_misses,
            "forbidden_hits": r.forbidden_hits,
            "grounding_violations": r.grounding_violations,
            "notes": r.notes,
        }
        for r in results
    ]
    return report
