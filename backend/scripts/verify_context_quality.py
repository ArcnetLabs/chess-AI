"""Context-quality verifier (the credential-free half of the phase 8 decision).

    python scripts/verify_context_quality.py --user-id 1

Answers "is the player context correct and safe to coach from?" against the
*real* prompts the coach sends, for one existing player. This is the half of the
train-or-not question that needs no LLM: if the context is already wrong, a model
baseline measures the wrong thing.

The probe set is the same one ``run_model_eval`` uses, so the two reports line up.

Exit codes: 0 = every context passed, 1 = at least one violation, 2 = no probes
(the user has no analysable history yet).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.services.evaluation.coach_probes import build_probes  # noqa: E402
from app.services.evaluation.context_quality import (  # noqa: E402
    summarise_context_checks,
    verify_context_quality,
)

EXIT_OK = 0
EXIT_VIOLATIONS = 1
EXIT_NO_PROBES = 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--json", help="write the full report to this path")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        probes = build_probes(db, args.user_id)
    finally:
        db.close()

    if not probes:
        print("No probes: this player has no position history to check yet.")
        return EXIT_NO_PROBES

    results = []
    for probe in probes:
        checks = verify_context_quality(
            probe.context, name=probe.name, expect_history=probe.expects_history
        )
        results.append(checks)
        status = "pass" if checks.passed else "FAIL"
        print(
            f"\n[{status}] {probe.name} ({len(probe.context)} chars, "
            f"expects_history={probe.expects_history})"
        )
        for check, ok in checks.checks.items():
            print(f"    {'ok  ' if ok else 'FAIL'} {check}")
        for violation in checks.violations:
            print(f"    -> {violation}")

    summary = summarise_context_checks(results)
    print(
        f"\ncontexts: {summary['contexts_passed']}/{summary['contexts']} passed, "
        f"checks {summary['checks_passed']}/{summary['checks_total']}"
    )

    # A player with no history makes every probe fall back to the absence path, so
    # a clean run would otherwise read as "context verified" when the history path
    # was never exercised. Say which one happened.
    history_probes = [probe for probe in probes if probe.expects_history]
    rendered = [probe for probe in history_probes if "Nothing on record" not in probe.context]
    if not history_probes:
        print("NOTE: no probe expected player history — only the absence path was checked.")
    elif not rendered:
        print("NOTE: probes expected history but none rendered any — history path unchecked.")

    for violation in summary["violations"]:
        print(f"  - {violation}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "user_id": args.user_id,
                    "summary": summary,
                    "contexts": [
                        {
                            "name": r.name,
                            "passed": r.passed,
                            "checks": r.checks,
                            "violations": r.violations,
                        }
                        for r in results
                    ],
                },
                handle,
                indent=2,
            )
        print(f"report written to {args.json}")

    return EXIT_OK if summary["contexts_passed"] == summary["contexts"] else EXIT_VIOLATIONS


if __name__ == "__main__":
    sys.exit(main())
