# Backend Operational Scripts

This directory holds **standalone diagnostic / smoke-test scripts** for the ChessIQ backend.

These are **not** part of the automated test suite — `pytest.ini` declares `testpaths = tests`, so pytest will not pick up anything in this folder. Each script is intended to be run manually (e.g. `python backend/scripts/test_db_connection.py`) to verify that an external dependency is reachable from the current environment.

## Scripts

| Script | Purpose |
| --- | --- |
| `test_db_connection.py` | Verifies the SQLAlchemy connection using the configured `DATABASE_URL`. |
| `test_supabase_connection.py` | Verifies connectivity to the configured Supabase instance. |
| `test_chesscom_api.py` | Smoke-tests the Chess.com API client (username lookup, profile fetch). |
| `test_celery_api.py` | Smoke-tests Celery task dispatching against the configured broker. |
| `test_redis_cache.py` | Exercises the Redis cache layer (set/get/expire) used by the Chess.com client. |
| `test_rate_limiting.py` | Exercises the Redis-backed per-user rate limiter on the Chess.com client. |
| `simulate_coach_journey.py` | E2E smoke test for the authenticated user → chat coach flow (health, profile, optional Chess.com link, session, message). |

## When to use

- After deploying to a new environment, to confirm external services are reachable.
- When debugging a "this works locally but not in env X" issue.
- After rotating credentials or upgrading a dependency client (Supabase, Celery, Redis).

## When **not** to use

- These scripts are **not** a substitute for the proper test suite. Run `python run_tests.py` (or `pytest`) for the real tests in `backend/tests/`.
- They are not run in CI.

## Conventions

- Each script must be runnable directly: `python backend/scripts/<name>.py` from the repo root, or `python scripts/<name>.py` from inside `backend/`.
- Scripts must load `.env` themselves (do not assume the FastAPI app has initialized).
- Scripts should print clear PASS/FAIL output and exit with a non-zero status on failure.

If you have an obsolete smoke-test you no longer need, archive it under `docs/archive/` with a `backend_scripts_` prefix rather than deleting it outright.
