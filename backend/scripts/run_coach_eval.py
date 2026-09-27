"""Evaluation harness entry point (offline, no engine and no model needed).

    python scripts/run_coach_eval.py                 # human-readable report
    python scripts/run_coach_eval.py --json report.json
    python scripts/run_coach_eval.py --baseline docs/audit/coaching-eval-baseline.json

Exits non-zero when the report misses the floors, so it can gate a change.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.services.evaluation.coach_eval import run_harness  # noqa: E402

# Floors the current system must clear. Deliberately conservative: the point is to
# catch regressions, not to flatter the system.
FLOORS = {
    "pattern_recall": 0.9,
    "pattern_precision": 0.9,
    "grounding_violations": 0,
    "cases_passed": None,  # all cases
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="write the full report to this path")
    parser.add_argument("--baseline", help="write a baseline snapshot to this path")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = run_harness(db)
    finally:
        db.close()

    print(f"cases: {report['cases_passed']}/{report['cases']} passed")
    print(
        f"patterns: {report['patterns_found']}/{report['patterns_expected']} found "
        f"(recall={report['pattern_recall']}, precision={report['pattern_precision']})"
    )
    print(
        f"false-pattern rate: {report['false_pattern_rate']} "
        f"({report['false_pattern_hits']} hits over {report['detected_patterns_total']} detected)"
    )
    print(f"grounding violations: {report['grounding_violations']}")

    failures = [c for c in report["case_results"] if not c["passed"]]
    for case in failures:
        print(f"  FAIL {case['name']} ({case['category']}): "
              f"missed={case['expected_misses']} forbidden={case['forbidden_hits']} "
              f"violations={case['grounding_violations']}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(f"wrote {args.json}")

    if args.baseline:
        snapshot = {
            key: value
            for key, value in report.items()
            if key not in ("case_results",)
        }
        with open(args.baseline, "w", encoding="utf-8") as handle:
            json.dump(snapshot, handle, indent=2)
        print(f"wrote baseline {args.baseline}")

    ok = True
    if report["cases_passed"] != report["cases"]:
        ok = False
    for key, floor in FLOORS.items():
        if floor is None:
            continue
        value = report.get(key)
        if value is None or value < floor:
            print(f"BELOW FLOOR: {key}={value} (floor {floor})")
            ok = False
    print("EVAL PASSED" if ok else "EVAL FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
