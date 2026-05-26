"""One-shot verification for Supabase Auth + Postgres configuration."""
from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env", override=True)
sys.path.insert(0, str(BACKEND_DIR))


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    for key in (
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_JWT_SECRET",
        "SECRET_KEY",
    ):
        val = os.getenv(key, "").strip()
        checks.append((f"env:{key}", bool(val), "set" if val else "MISSING"))

    try:
        from sqlalchemy import create_engine, text

        url = os.environ["DATABASE_URL"]
        engine = create_engine(
            url, pool_pre_ping=True, connect_args={"connect_timeout": 20}
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            rows = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' ORDER BY table_name"
                )
            ).fetchall()
        names = {r[0] for r in rows}
        expected = {"users", "games", "game_analyses", "user_insights"}
        missing = expected - names
        checks.append(("db:connect", True, f"ok ({len(names)} public tables)"))
        checks.append(
            (
                "db:schema",
                not missing,
                "missing: " + ", ".join(sorted(missing)) if missing else "core tables present",
            )
        )
    except Exception as exc:
        checks.append(("db:connect", False, str(exc)[:240]))

    try:
        import jwt as pyjwt

        from app.core.config import settings
        from app.services.auth.auth_service import AuthService

        sub = str(uuid.uuid4())
        token = pyjwt.encode(
            {
                "sub": sub,
                "email": "verify@test.local",
                "aud": settings.SUPABASE_JWT_AUDIENCE,
                "iss": settings.SUPABASE_URL + "/auth/v1",
                "exp": int(time.time()) + 3600,
                "iat": int(time.time()),
            },
            settings.SUPABASE_JWT_SECRET,
            algorithm=settings.SUPABASE_JWT_ALGORITHM,
        )
        claims = AuthService.verify_jwt(token)
        checks.append(
            (
                "auth:jwt_local",
                claims.get("sub") == sub,
                "local JWT verify ok",
            )
        )
    except Exception as exc:
        checks.append(("auth:jwt_local", False, str(exc)[:240]))

    try:
        from app.core.supabase_client import get_supabase_admin

        client = get_supabase_admin()
        client.auth.admin.list_users(page=1, per_page=1)
        checks.append(("auth:service_role", True, "admin API reachable"))
    except Exception as exc:
        checks.append(("auth:service_role", False, str(exc)[:240]))

    fe_url = None
    fe_path = BACKEND_DIR.parent / "frontend" / ".env.local"
    if fe_path.exists():
        for line in fe_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("NEXT_PUBLIC_SUPABASE_URL="):
                fe_url = line.split("=", 1)[1].strip()
                break
    be_url = os.getenv("SUPABASE_URL", "")
    checks.append(
        (
            "align:supabase_url",
            fe_url == be_url,
            f"frontend and backend match ({be_url})",
        )
    )

    print("=== ChessIQ Supabase verification ===")
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
