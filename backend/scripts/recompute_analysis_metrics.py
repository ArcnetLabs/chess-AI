"""Rebuild stored analysis metrics from the move-facts layer.

    python scripts/recompute_analysis_metrics.py --user-id 33            # dry run
    python scripts/recompute_analysis_metrics.py --user-id 33 --apply

``game_analyses.user_acpl``, ``accuracy_percentage``, the three phase ACPLs and
every stored move classification were derived from ``MoveAnalysis.evaluation_change``
while that value compared evaluations taken in different frames (the analyzer
flipped the running evaluation in place; see ``unified_analyzer._analyze_all_moves``
for the fix and the live evidence). The result was an ACPL roughly 4x too high on
average — up to 35x — a mean accuracy of 38.6% instead of 71.4%, and blunder
counts wrong in both directions (26 "blunders" in a game whose moves lost 30cp
each, and 0 recorded in a game that lost nine pieces).

``game_moves`` holds the same information computed correctly — ``cp_loss`` per
ply, in the mover's own frame — so the player-facing numbers can be rebuilt from
it without re-running Stockfish. The classification rules and the ACPL→accuracy
mapping are imported from the analyzer, so this script cannot drift from the
engine path.

What it rewrites, per affected game:

* ``game_moves.classification`` (it used to copy the miscounted value)
* ``game_analyses``: ``user_acpl``, ``accuracy_percentage``, the move-class counts,
  the three phase ACPLs, and the ``evaluations`` / ``blunder_moves`` /
  ``critical_positions`` JSON payloads

Patterns and the player profile are derived from this data, so re-run detection
afterwards — the same note as ``scripts/recompute_phases.py``:

    python -c "from app.core.database import SessionLocal; \\
from app.services.patterns.pattern_engine import run_pattern_detection; \\
db = SessionLocal(); run_pattern_detection(db, <user_id>, persist=True)"
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.models.game import Game, GameAnalysis  # noqa: E402
from app.models.game_move import GameMove  # noqa: E402
from app.services.analysis.unified_analyzer import (  # noqa: E402
    acpl_to_accuracy,
    classify_move,
)

EXIT_OK = 0
EXIT_NO_OP = 1

#: ``critical_positions`` used this cutoff on the (unclamped) evaluation change.
CRITICAL_LOSS_CP = 150.0


def _mean(values: List[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _recompute_for_game(
    rows: List[GameMove],
) -> Dict[str, object]:
    """Everything derivable from one game's move facts."""
    user_moves = [r for r in rows if r.is_user_move]
    losses = [float(r.cp_loss or 0) for r in user_moves]
    acpl = _mean(losses)

    classifications: Dict[str, str] = {}
    for row in rows:
        classifications[row.ply] = classify_move(
            float(row.cp_loss or 0),
            (row.move_uci or "") == (row.best_move_uci or ""),
        )

    counts = {
        'brilliant_moves': 0,
        'great_moves': 0,
        'best_moves': 0,
        'excellent_moves': 0,
        'good_moves': 0,
        'inaccuracies': 0,
        'mistakes': 0,
        'blunders': 0,
    }
    label_to_field = {
        'brilliant': 'brilliant_moves',
        'great': 'great_moves',
        'best': 'best_moves',
        'excellent': 'excellent_moves',
        'good': 'good_moves',
        'inaccuracy': 'inaccuracies',
        'mistake': 'mistakes',
        'blunder': 'blunders',
    }
    for row in user_moves:
        counts[label_to_field[classifications[row.ply]]] += 1

    phase_acpl = {}
    for phase in ('opening', 'middlegame', 'endgame'):
        phase_acpl[phase] = _mean(
            [float(r.cp_loss or 0) for r in user_moves if r.phase == phase]
        )

    return {
        'user_acpl': acpl,
        'accuracy_percentage': acpl_to_accuracy(acpl) if acpl is not None else None,
        'counts': counts,
        'phase_acpl': phase_acpl,
        'classifications': classifications,
        'user_moves': user_moves,
    }


def _rewrite_json(
    evaluations: Optional[list],
    rows: List[GameMove],
    computed: Dict[str, object],
) -> tuple:
    """Correct the stored move JSON, and rebuild the two derived lists."""
    classifications = computed['classifications']
    losses = {r.ply: float(r.cp_loss or 0) for r in rows}
    is_user = {r.ply: bool(r.is_user_move) for r in rows}

    fixed: List[dict] = []
    for index, entry in enumerate(evaluations or []):
        ply = index + 1
        if not isinstance(entry, dict) or ply not in losses:
            fixed.append(entry)
            continue
        updated = dict(entry)
        updated['evaluation_change'] = round(losses[ply], 1)
        updated['classification'] = classifications[ply]
        fixed.append(updated)

    blunder_moves = [
        entry
        for index, entry in enumerate(fixed)
        if isinstance(entry, dict)
        and is_user.get(index + 1)
        and classifications.get(index + 1) in ('mistake', 'blunder')
    ]
    critical_positions = [
        entry
        for index, entry in enumerate(fixed)
        if isinstance(entry, dict)
        and is_user.get(index + 1)
        and losses.get(index + 1, 0.0) > CRITICAL_LOSS_CP
    ]
    return fixed, blunder_moves, critical_positions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-id', type=int, default=None, help='limit to one user')
    parser.add_argument('--game-id', type=int, default=None, help='limit to one game')
    parser.add_argument('--limit', type=int, default=None, help='stop after N games')
    parser.add_argument(
        '--apply',
        action='store_true',
        help='write the changes (default is a dry run that only reports)',
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = (
            db.query(GameAnalysis, Game)
            .join(Game, Game.id == GameAnalysis.game_id)
            .order_by(GameAnalysis.game_id)
        )
        if args.user_id is not None:
            query = query.filter(Game.user_id == args.user_id)
        if args.game_id is not None:
            query = query.filter(GameAnalysis.game_id == args.game_id)
        if args.limit:
            query = query.limit(args.limit)

        changed_games = 0
        seen_games = 0
        before_acpl: List[float] = []
        after_acpl: List[float] = []
        before_blunders = 0
        after_blunders = 0

        for analysis, game in query.all():
            rows = (
                db.query(GameMove)
                .filter(GameMove.game_id == game.id)
                .order_by(GameMove.ply)
                .all()
            )
            if not rows:
                continue

            seen_games += 1
            computed = _recompute_for_game(rows)
            acpl = computed['user_acpl']
            if acpl is None:
                continue

            stored_acpl = float(analysis.user_acpl or 0)
            before_acpl.append(stored_acpl)
            after_acpl.append(float(acpl))
            before_blunders += int(analysis.blunders or 0)
            after_blunders += int(computed['counts']['blunders'])

            if abs(stored_acpl - float(acpl)) < 0.05:
                continue

            changed_games += 1
            print(
                f"game {game.id:>6}: acpl {stored_acpl:>8.1f} -> {float(acpl):>7.1f} | "
                f"accuracy {float(analysis.accuracy_percentage or 0):>5.1f}% -> "
                f"{float(computed['accuracy_percentage'] or 0):>5.1f}% | "
                f"blunders {int(analysis.blunders or 0)} -> {computed['counts']['blunders']}"
            )

            if not args.apply:
                continue

            counts = computed['counts']
            for field, value in counts.items():
                setattr(analysis, field, value)
            analysis.user_acpl = round(float(acpl), 2)
            analysis.accuracy_percentage = round(float(computed['accuracy_percentage']), 2)
            for phase, value in computed['phase_acpl'].items():
                setattr(
                    analysis,
                    f'{phase}_acpl',
                    round(float(value), 2) if value is not None else None,
                )

            evaluations, blunders, critical = _rewrite_json(
                analysis.evaluations, rows, computed
            )
            analysis.evaluations = evaluations
            analysis.blunder_moves = blunders
            analysis.critical_positions = critical

            for row in rows:
                row.classification = computed['classifications'][row.ply]

            db.commit()

        print(
            f"\n{seen_games} games with move facts, {changed_games} need rewriting"
            + (" (applied)" if args.apply else " (dry run — pass --apply to write)")
        )
        if before_acpl:
            print(
                f"mean acpl {sum(before_acpl) / len(before_acpl):.1f} -> "
                f"{sum(after_acpl) / len(after_acpl):.1f}; "
                f"blunders {before_blunders} -> {after_blunders}"
            )
        return EXIT_OK if changed_games else EXIT_NO_OP
    finally:
        db.close()


if __name__ == '__main__':
    raise SystemExit(main())
