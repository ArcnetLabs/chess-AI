"""P0 infrastructure verification — DB, Redis, Celery, Alembic, env consistency.

Usage (from backend/):
    .venv\\Scripts\\python.exe scripts\\verify_infrastructure.py

Exit 0 = all required checks passed.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env", override=True)
sys.path.insert(0, str(BACKEND_DIR))


def _check(name: str, ok: bool, detail: str) -> tuple[str, bool, str]:
    return (name, ok, detail)


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    # --- Environment consistency ---------------------------------------------
    db_url = os.getenv("DATABASE_URL", "").strip()
    checks.append(_check("env:DATABASE_URL", bool(db_url), "set" if db_url else "MISSING"))

    if db_url.startswith("sqlite") and os.getenv("TESTING") != "1":
        checks.append(
            _check(
                "db:no_sqlite_runtime",
                False,
                "SQLite DATABASE_URL outside pytest — forbidden",
            )
        )
    elif db_url:
        checks.append(
            _check(
                "db:no_sqlite_runtime",
                not db_url.startswith("sqlite") or os.getenv("TESTING") == "1",
                "PostgreSQL URL (or pytest in-memory)",
            )
        )

    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379")
    checks.append(
        _check(
            "env:redis_config",
            bool(redis_host),
            f"{redis_host}:{redis_port}",
        )
    )

    # --- Database (fail-fast module) -----------------------------------------
    try:
        from sqlalchemy import text
        from app.core.database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            version = conn.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar_one_or_none()
        checks.append(_check("db:connect", True, "PostgreSQL reachable"))
        checks.append(
            _check(
                "db:alembic_version",
                version is not None,
                f"revision={version}" if version else "alembic_version empty — run alembic upgrade head",
            )
        )
    except Exception as exc:
        msg = str(exc)
        if "alembic_version" in msg or "does not exist" in msg:
            checks.append(_check("db:connect", True, "connected (alembic_version table missing)"))
            checks.append(
                _check(
                    "db:alembic_version",
                    False,
                    "run: cd backend && alembic upgrade head",
                )
            )
        else:
            checks.append(_check("db:connect", False, msg[:240]))

    # --- No create_all on startup --------------------------------------------
    try:
        import inspect
        from app import __main__ as main_mod

        src = inspect.getsource(main_mod)
        checks.append(
            _check(
                "db:no_create_all",
                "create_all" not in src,
                "startup does not call Base.metadata.create_all",
            )
        )
    except Exception as exc:
        checks.append(_check("db:no_create_all", False, str(exc)[:120]))

    # --- Redis ---------------------------------------------------------------
    try:
        import redis

        client = redis.Redis(
            host=redis_host,
            port=int(redis_port),
            db=int(os.getenv("REDIS_DB", "0")),
            decode_responses=True,
            socket_connect_timeout=2,
        )
        client.ping()
        checks.append(_check("redis:ping", True, "PONG"))
    except Exception as exc:
        env = os.getenv("ENVIRONMENT", "development")
        if env in ("production", "staging"):
            checks.append(_check("redis:ping", False, str(exc)[:240]))
        else:
            checks.append(
                _check(
                    "redis:ping",
                    True,
                    f"skipped in {env} (optional locally): {str(exc)[:80]}",
                )
            )

    # --- Celery app boot -----------------------------------------------------
    try:
        from app.celery_app import celery_app

        checks.append(
            _check(
                "celery:import",
                celery_app.main == "chess_ai",
                f"broker={celery_app.conf.broker_url}",
            )
        )
        registered = list(celery_app.tasks.keys())
        has_analysis = any("analyze_game_task" in t for t in registered)
        checks.append(
            _check(
                "celery:tasks",
                has_analysis,
                "analysis tasks registered" if has_analysis else "missing analysis tasks",
            )
        )
    except Exception as exc:
        checks.append(_check("celery:import", False, str(exc)[:240]))

    # --- Render / compose config sanity --------------------------------------
    repo_root = BACKEND_DIR.parent
    render = (repo_root / "render.yaml").read_text(encoding="utf-8")
    compose = (repo_root / "docker-compose.yml").read_text(encoding="utf-8")

    checks.append(
        _check(
            "deploy:render_entrypoint",
            "uvicorn app:app" in render and "app.main:app" not in render,
            "uvicorn app:app",
        )
    )
    checks.append(
        _check(
            "deploy:render_alembic",
            "alembic upgrade head" in render,
            "build runs alembic upgrade head",
        )
    )
    checks.append(
        _check(
            "deploy:render_no_pserv_db",
            "type: pserv" not in render and "databases:" not in render,
            "Supabase DATABASE_URL (no Render Postgres pserv)",
        )
    )
    checks.append(
        _check(
            "deploy:render_celery_worker",
            "chess-insight-celery" in render and "app.celery_app" in render,
            "Celery worker service defined in render.yaml",
        )
    )
    checks.append(
        _check(
            "deploy:compose_celery_module",
            "app.celery_app" in compose and "app.workers.celery_app" not in compose,
            "docker-compose uses app.celery_app",
        )
    )

    # --- Alembic CLI (optional if DB down) -----------------------------------
    if db_url and not db_url.startswith("sqlite"):
        try:
            alembic_bin = BACKEND_DIR / ".venv" / "Scripts" / "alembic.exe"
            cmd = [str(alembic_bin) if alembic_bin.exists() else "alembic", "current"]
            result = subprocess.run(
                cmd,
                cwd=BACKEND_DIR,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = (result.stdout or result.stderr).strip()
            # Alembic prints revision to stdout on success
            ok = result.returncode == 0 and ("0005" in output or "head" in output.lower() or "(head)" in output)
            checks.append(
                _check(
                    "alembic:current",
                    ok,
                    output[:120] if output else f"exit {result.returncode}",
                )
            )
        except Exception as exc:
            checks.append(_check("alembic:current", False, str(exc)[:120]))

    print("=== ChessIQ infrastructure verification ===")
    failed = 0
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{status}] {name}: {detail}")
    print("---")
    if failed:
        print(f"RESULT: {failed} check(s) FAILED")
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
