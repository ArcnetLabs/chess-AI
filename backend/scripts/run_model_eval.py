"""Model-side evaluation runner (phase 8's decision input).

    python scripts/run_model_eval.py --user-id 1
    python scripts/run_model_eval.py --user-id 1 --json model_eval.json

Requires LLM credentials in the environment (the same ones the app uses:
``LLM_LOCAL_API_KEY`` / ``OPENROUTER_API_KEY`` / ``OPENAI_API_KEY``). Without them
the script still assembles and prints the exact prompts it would send, and exits
with code 2 to mark "prerequisite missing" rather than "evaluation failed" — the
distinction matters when reading a report later.

Why the model baseline matters: the architecture doc allows fine-tuning only if
the model fails *despite* correct context. The phase 7 harness verified the
context is correct; this measures what the model does with it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.services.evaluation.coach_probes import run_model_eval  # noqa: E402

EXIT_OK = 0
EXIT_BELOW_FLOOR = 1
EXIT_NO_PROVIDER = 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--json", help="write the full report to this path")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = run_model_eval(db, args.user_id)
    finally:
        db.close()

    print(f"provider: {report['provider']}")
    print(f"probes: {report.get('probes')} scored: {report.get('scored')} "
          f"passed: {report.get('passed')}")

    if report["provider"] == "unavailable":
        print(f"\n{report.get('reason', 'no provider')}")
        for prompt in report.get("prompts", []):
            print(f"\n--- probe {prompt['name']} ({prompt['context_chars']} chars, "
                  f"expects_history={prompt['expects_history']}) ---")
            print(prompt["context_preview"])
        if args.json:
            with open(args.json, "w", encoding="utf-8") as handle:
                json.dump(report, handle, indent=2)
            print(f"\nwrote {args.json}")
        return EXIT_NO_PROVIDER

    for result in report["results"]:
        status = "pass" if result["passed"] else "FAIL"
        print(f"  [{status}] {result['name']}")
        for violation in result["violations"]:
            print(f"      - {violation}")
        if not result["passed"] and result.get("reply_excerpt"):
            # Print what the model actually said, so a failure in a build log can be
            # judged rather than trusted.
            print(f"      reply: {result['reply_excerpt'][:400]}")
    if report.get("checks"):
        print("\nper-check pass counts:")
        for check, count in report["checks"].items():
            print(f"  {check}: {count}/{report['scored']}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(f"wrote {args.json}")

    # The decision input: a model that passes every deterministic check while
    # receiving correct context is evidence *against* fine-tuning.
    return EXIT_OK if report["passed"] == report["scored"] else EXIT_BELOW_FLOOR


if __name__ == "__main__":
    raise SystemExit(main())
