"""Preflight checks for the Render Celery worker before starting the process.

Usage (from backend/):
    python scripts/verify_celery_worker_env.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


def main() -> int:
    errors: list[str] = []

    try:
        from app.core.config import settings
    except Exception as exc:
        print(f"FATAL: settings failed to load: {exc}")
        return 1

    if not settings.DATABASE_URL:
        errors.append(
            "DATABASE_URL is missing on this service. "
            "Set the same Supabase Postgres URL on chess-insight-celery as on the web service."
        )

    if settings.ENVIRONMENT in ("production", "staging"):
        try:
            import redis

            client = redis.Redis.from_url(
                settings.REDIS_URL, decode_responses=True, socket_connect_timeout=3
            )
            client.ping()
        except Exception as exc:
            errors.append(f"Redis unreachable at {settings.REDIS_URL}: {exc}")

    try:
        from app.celery_app import celery_app

        if celery_app.main != "chess_ai":
            errors.append(f"Unexpected Celery app name: {celery_app.main}")
    except Exception as exc:
        errors.append(f"Celery import failed: {exc}")

    if errors:
        print("=== Celery worker preflight FAILED ===")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("=== Celery worker preflight OK ===")
    print(f"  broker={settings.CELERY_BROKER_URL}")
    print(f"  stockfish={settings.STOCKFISH_PATH or '(auto-detect)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
