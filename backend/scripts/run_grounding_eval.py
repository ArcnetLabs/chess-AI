#!/usr/bin/env python3
"""Manual smoke script for coach context grounding evaluation (P3-CM-05)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

from app.core.database import SessionLocal
from app.services.coaching.grounding_eval_service import (
    evaluate_coach_context,
    load_grounding_eval_set,
)


def main() -> int:
    cases = load_grounding_eval_set()
    if not cases:
        print("FAIL: grounding eval set is empty")
        return 1

    print(f"Loaded {len(cases)} grounding eval cases")

    user_id_raw = input("Enter user_id to evaluate (or blank to skip DB run): ").strip()
    if not user_id_raw:
        print("PASS: dataset load only (no user evaluation requested)")
        return 0

    try:
        user_id = int(user_id_raw)
    except ValueError:
        print("FAIL: user_id must be an integer")
        return 1

    db = SessionLocal()
    try:
        result = evaluate_coach_context(db, user_id, cases, top_patterns=15)
    finally:
        db.close()

    print(f"Pass count: {result.pass_count}/{result.total}")
    print(f"Pass rate: {result.pass_rate:.1%}")

    failed = [item for item in result.case_results if not item.passed]
    if failed:
        print("\nFailed cases:")
        for item in failed[:10]:
            print(f"  - {item.case_id}: {item.question}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more")

    if result.pass_rate >= 0.9:
        print("PASS: meets Phase 3 exit gate (>=90%)")
        return 0

    print("WARN: below Phase 3 exit gate (>=90%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
