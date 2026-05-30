#!/usr/bin/env python3
"""Obtain a Supabase access_token for local API smoke tests (passwordless).

Uses the service role to generate a magic link, then verifies it to produce
a JWT without a password (FR-AUTH-1).

Requires in backend/.env:

    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    SUPABASE_TEST_EMAIL=you@example.com
    SUPABASE_TEST_CHESSCOM_USERNAME=gh_wilder   # optional metadata

Usage:
    python backend/scripts/get_supabase_jwt.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")


def main() -> int:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    email = os.getenv("SUPABASE_TEST_EMAIL", "").strip()
    chesscom = os.getenv("SUPABASE_TEST_CHESSCOM_USERNAME", "").strip().lower()
    redirect = os.getenv(
        "SUPABASE_MAGIC_LINK_REDIRECT",
        "http://localhost:3000/auth/callback",
    )

    missing = [
        name
        for name, val in [
            ("SUPABASE_URL", url),
            ("SUPABASE_SERVICE_ROLE_KEY", service_key),
            ("SUPABASE_TEST_EMAIL", email),
        ]
        if not val
    ]
    if missing:
        print("Missing in backend/.env:", ", ".join(missing))
        print()
        print("Or sign in via the app (no password):")
        print("  1. http://localhost:3000/auth/login")
        print("  2. Email + Chess.com username → click link in email")
        print("  3. DevTools → Application → Cookies → sb-*-auth-token → access_token")
        return 1

    try:
        from supabase import create_client
    except ImportError:
        print("Install supabase: pip install supabase")
        return 1

    admin = create_client(url, service_key)
    user_metadata = {"chesscom_username": chesscom} if chesscom else {}

    link_resp = admin.auth.admin.generate_link(
        {
            "type": "magiclink",
            "email": email,
            "options": {
                "redirect_to": redirect,
                "data": user_metadata,
            },
        }
    )

    props = getattr(link_resp, "properties", None) or link_resp.get("properties")
    if props is None:
        print("Unexpected generate_link response:", link_resp)
        return 1

    hashed = getattr(props, "hashed_token", None) or props.get("hashed_token")
    if not hashed:
        action = getattr(props, "action_link", None) or props.get("action_link")
        print("Open this link in a browser to sign in (no password):")
        print(action or props)
        return 0

    verify = admin.auth.verify_otp(
        {
            "type": "magiclink",
            "email": email,
            "token_hash": hashed,
        }
    )

    session = getattr(verify, "session", None)
    if session is None and isinstance(verify, dict):
        session = verify.get("session")
    access = getattr(session, "access_token", None) if session else None
    if access is None and isinstance(session, dict):
        access = session.get("access_token")

    if not access:
        print("verify_otp did not return access_token:", verify)
        return 1

    print(f"Signed in as: {email}")
    if chesscom:
        print(f"Chess.com username (metadata): {chesscom}")
    print()
    print("access_token:")
    print(access)
    print()
    print("Example:")
    print(
        "  python backend/scripts/simulate_coach_journey.py "
        f'--jwt "<token>" --chesscom-username {chesscom or "yourname"}'
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
