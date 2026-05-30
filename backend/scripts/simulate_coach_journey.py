#!/usr/bin/env python3
"""Manual E2E smoke script for the user → chat coach journey.

Usage (from repo root):
    python backend/scripts/simulate_coach_journey.py --jwt "<access_token>"

Usage (from backend/):
    python scripts/simulate_coach_journey.py --jwt "<access_token>"

Exit 0 when the chat message step succeeds; exit 1 on any failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")

DEFAULT_MESSAGE = "How can I improve my endgames?"
JWT_SETUP_INSTRUCTIONS = (
    "Passwordless sign-in: /auth/login (email + Chess.com username), "
    "click the magic link, then copy access_token from the session cookie "
    "OR run: python backend/scripts/get_supabase_jwt.py\n"
    "Re-run with: --jwt \"<access_token>\""
)

TEMPLATE_MARKER = "That's a great question about chess improvement!"


def normalize_base_url(base_url: str) -> str:
    """Ensure base URL includes /api/v1 without a trailing slash."""
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/api/v1"):
        return trimmed
    return f"{trimmed}/api/v1"


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulate the authenticated user → chat coach journey.",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--jwt",
        default=None,
        help="Supabase access_token (required unless --mock)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use canned responses instead of live HTTP (no JWT required)",
    )
    parser.add_argument(
        "--chesscom-username",
        default=None,
        help="Optional Chess.com username to link before chatting",
    )
    parser.add_argument(
        "--message",
        default=DEFAULT_MESSAGE,
        help=f"Coach message to send (default: {DEFAULT_MESSAGE!r})",
    )
    return parser.parse_args(argv)


def auth_headers(jwt: Optional[str]) -> dict[str, str]:
    if not jwt:
        return {}
    return {"Authorization": f"Bearer {jwt}"}


def print_step(name: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    line = f"[{status}] {name}"
    if detail:
        line = f"{line} — {detail}"
    print(line)


def is_non_template_response(response_payload: dict[str, Any]) -> bool:
    """True when the coach reply looks LLM-backed or otherwise non-template."""
    if response_payload.get("used_llm"):
        return True
    if response_payload.get("llm_provider"):
        return True

    message = (response_payload.get("message") or "").strip()
    if not message:
        return False

    return TEMPLATE_MARKER not in message


@dataclass
class StepResult:
    name: str
    passed: bool
    detail: str = ""


def _real_request(
    method: str,
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    json_body: Optional[dict[str, Any]] = None,
    timeout: int = 30,
) -> requests.Response:
    return requests.request(
        method,
        url,
        headers=headers,
        json=json_body,
        timeout=timeout,
    )


def _mock_request(
    method: str,
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    json_body: Optional[dict[str, Any]] = None,
    timeout: int = 30,
) -> requests.Response:
    """Return canned HTTP responses for offline script validation."""
    response = requests.Response()
    response.status_code = 200
    response._content = b"{}"

    if url.endswith("/chat/health"):
        response._content = json.dumps(
            {
                "status": "healthy",
                "service": "chess-coach-chatbot",
                "stockfish": "available",
                "active_sessions": 0,
            }
        ).encode()
    elif url.endswith("/users/me") and method.upper() == "GET":
        response._content = json.dumps(
            {
                "id": 1,
                "chesscom_username": "mockplayer",
                "email": "mock@example.com",
            }
        ).encode()
    elif url.endswith("/users/me/link-chesscom") and method.upper() == "POST":
        username = (json_body or {}).get("chesscom_username", "mockplayer")
        response._content = json.dumps(
            {
                "id": 1,
                "chesscom_username": username,
                "is_chesscom_connected": True,
            }
        ).encode()
    elif url.endswith("/chat/session") and method.upper() == "POST":
        response._content = json.dumps(
            {
                "success": True,
                "session_id": "mock-session-001",
                "message": "Welcome to ChessIQ coach.",
            }
        ).encode()
    elif url.endswith("/chat/message") and method.upper() == "POST":
        response._content = json.dumps(
            {
                "success": True,
                "session_id": "mock-session-001",
                "response": {
                    "message": "Focus on king activity and pawn structure in endgames.",
                    "intent": "general_question",
                    "used_llm": True,
                    "llm_provider": "mock",
                    "cited_pattern_ids": [42, 43],
                    "suggestions": ["Analyze my recent game"],
                },
            }
        ).encode()
    else:
        response.status_code = 404
        response._content = json.dumps({"detail": f"Unhandled mock route: {method} {url}"}).encode()

    return response


def run_coach_journey(
    *,
    api_base: str,
    jwt: Optional[str],
    message: str,
    chesscom_username: Optional[str],
    mock: bool = False,
    request_fn: Optional[Callable[..., requests.Response]] = None,
    timeout: int = 30,
) -> tuple[bool, list[StepResult]]:
    """Execute journey steps and return overall success plus per-step results."""
    if mock and not jwt:
        jwt = "mock-jwt"

    if request_fn is None:
        request_fn = _mock_request if mock else _real_request

    results: list[StepResult] = []
    all_passed = True
    session_id: Optional[str] = None

    def record(name: str, passed: bool, detail: str = "") -> None:
        nonlocal all_passed
        results.append(StepResult(name=name, passed=passed, detail=detail))
        print_step(name, passed, detail)
        if not passed:
            all_passed = False

    # Step 1: chat health (no auth)
    health_url = urljoin(f"{api_base}/", "chat/health")
    try:
        health_resp = request_fn("GET", health_url, timeout=timeout)
        health_ok = health_resp.status_code == 200
        health_detail = f"status={health_resp.status_code}"
        if health_ok:
            payload = health_resp.json()
            health_detail = f"service={payload.get('service', 'unknown')}, status={payload.get('status')}"
        record("GET /chat/health", health_ok, health_detail)
    except requests.RequestException as exc:
        record("GET /chat/health", False, str(exc))

    # Step 2: current user profile
    if not jwt:
        print(JWT_SETUP_INSTRUCTIONS)
        record("GET /users/me", False, "skipped — no JWT provided")
    else:
        me_url = urljoin(f"{api_base}/", "users/me")
        try:
            me_resp = request_fn(
                "GET",
                me_url,
                headers=auth_headers(jwt),
                timeout=timeout,
            )
            me_ok = me_resp.status_code == 200
            me_detail = f"status={me_resp.status_code}"
            if me_ok:
                me_payload = me_resp.json()
                me_detail = (
                    f"user_id={me_payload.get('id')}, "
                    f"chesscom={me_payload.get('chesscom_username') or 'not linked'}"
                )
            record("GET /users/me", me_ok, me_detail)
        except requests.RequestException as exc:
            record("GET /users/me", False, str(exc))

    # Step 3: optional Chess.com link
    if chesscom_username:
        if not jwt:
            record(
                "POST /users/me/link-chesscom",
                False,
                "skipped — no JWT provided",
            )
        else:
            link_url = urljoin(f"{api_base}/", "users/me/link-chesscom")
            try:
                link_resp = request_fn(
                    "POST",
                    link_url,
                    headers=auth_headers(jwt),
                    json_body={"chesscom_username": chesscom_username},
                    timeout=timeout,
                )
                link_ok = link_resp.status_code == 200
                link_detail = f"status={link_resp.status_code}"
                if link_ok:
                    link_payload = link_resp.json()
                    link_detail = f"linked={link_payload.get('chesscom_username')}"
                elif link_resp.text:
                    link_detail = f"status={link_resp.status_code}, body={link_resp.text[:120]}"
                record("POST /users/me/link-chesscom", link_ok, link_detail)
            except requests.RequestException as exc:
                record("POST /users/me/link-chesscom", False, str(exc))

    # Step 4: create chat session
    if not jwt:
        record("POST /chat/session", False, "skipped — no JWT provided")
    else:
        session_url = urljoin(f"{api_base}/", "chat/session")
        try:
            session_resp = request_fn(
                "POST",
                session_url,
                headers=auth_headers(jwt),
                json_body={},
                timeout=timeout,
            )
            session_ok = session_resp.status_code == 200
            session_detail = f"status={session_resp.status_code}"
            if session_ok:
                session_payload = session_resp.json()
                session_id = session_payload.get("session_id")
                session_detail = f"session_id={session_id}"
                session_ok = bool(session_id)
            record("POST /chat/session", session_ok, session_detail)
        except requests.RequestException as exc:
            record("POST /chat/session", False, str(exc))

    # Step 5: send chat message
    chat_success = False
    if not jwt:
        record("POST /chat/message", False, "skipped — no JWT provided")
    elif not session_id:
        record("POST /chat/message", False, "skipped — no session_id")
    else:
        message_url = urljoin(f"{api_base}/", "chat/message")
        try:
            message_resp = request_fn(
                "POST",
                message_url,
                headers=auth_headers(jwt),
                json_body={"message": message, "session_id": session_id},
                timeout=timeout,
            )
            message_ok = message_resp.status_code == 200
            message_detail = f"status={message_resp.status_code}"
            if message_ok:
                message_payload = message_resp.json()
                coach_response = message_payload.get("response") or {}
                non_template = is_non_template_response(coach_response)
                cited = coach_response.get("cited_pattern_ids") or []
                cited_text = f"cited_pattern_ids={cited}" if cited else "cited_pattern_ids=(none)"
                llm_text = f"used_llm={coach_response.get('used_llm', False)}"
                preview = (coach_response.get("message") or "")[:80]
                message_detail = f"{llm_text}, {cited_text}, preview={preview!r}"
                message_ok = message_payload.get("success", True) and bool(
                    coach_response.get("message")
                )
                if not non_template:
                    message_detail = f"{message_detail}; template fallback detected"
                chat_success = message_ok and non_template
            elif message_resp.text:
                message_detail = f"status={message_resp.status_code}, body={message_resp.text[:120]}"
            record("POST /chat/message", chat_success, message_detail)
        except requests.RequestException as exc:
            record("POST /chat/message", False, str(exc))

    return chat_success, results


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    if not args.jwt and not args.mock:
        print("ERROR: --jwt is required unless --mock is set.")
        print(JWT_SETUP_INSTRUCTIONS)

    api_base = normalize_base_url(args.base_url)

    print("=" * 70)
    print("CHESSIQ COACH JOURNEY SMOKE TEST")
    print("=" * 70)
    print(f"API base: {api_base}")
    print(f"Mock mode: {args.mock}")
    print(f"Message: {args.message!r}")
    if args.chesscom_username:
        print(f"Chess.com username: {args.chesscom_username}")
    print()

    chat_success, _ = run_coach_journey(
        api_base=api_base,
        jwt=args.jwt,
        message=args.message,
        chesscom_username=args.chesscom_username,
        mock=args.mock,
    )

    print()
    if chat_success:
        print("Overall: PASS — chat message succeeded")
        return 0

    print("Overall: FAIL — chat message did not succeed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
