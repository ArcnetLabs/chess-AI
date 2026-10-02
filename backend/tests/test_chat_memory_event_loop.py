"""Regression: chat-memory extraction must survive repeated Celery invocations.

Production defect (user 34, session ``e56bf37b-69ef-47c3-a343-aaf9d34e33a9``,
2026-09-29 17:20:59 UTC): every ``extract_chat_memories_task`` run after the
first one in a worker process reported ``status='failed'`` with
``reason='Event loop is closed'``, so coaching memories were never extracted
and the longitudinal coaching memory never accumulated.

Root cause: ``app.services.coaching.embedding_service`` cached a single
module-level ``httpx.AsyncClient``. Celery reaches that service through
``embed_texts_sync``, which runs each call on its own fresh ``asyncio.run``
loop, so the second invocation reused a client whose keep-alive connection
belonged to the loop the first invocation had already closed — the pooled
socket's asyncio transport then raised ``RuntimeError: Event loop is closed``.

These tests drive the real socket path on purpose: patching ``httpx`` or
``embed_texts_sync`` would hide the defect, because the failure needs a real
loop-bound connection to be pooled and then reused.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.chat import ChatSessionRecord
from app.models.semantic_memory import SemanticMemory
from app.models.user import User
from app.services.chat import ChatMessage, MessageRole
from app.services.coaching.embedding_service import EMBEDDING_DIM, embed_texts_sync
from app.tasks.chat_memory_tasks import extract_chat_memories_task

SESSION_ID = "e56bf37b-69ef-47c3-a343-aaf9d34e33a9"
ASKED_AT = datetime(2026, 9, 29, 17, 19, 0)


class _EmbeddingsHandler(BaseHTTPRequestHandler):
    """Minimal OpenAI-compatible ``/embeddings`` endpoint (HTTP/1.1 keep-alive)."""

    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler API
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length) or b"{}")
        body = json.dumps(
            {
                "data": [
                    {"index": index, "embedding": [0.25] * EMBEDDING_DIM}
                    for index, _ in enumerate(payload.get("input") or [])
                ]
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # keep pytest output clean
        pass


@pytest.fixture
def embeddings_endpoint(monkeypatch):
    """Point the embedding client at a real localhost server, not a mock."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _EmbeddingsHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(
        settings, "OPENAI_API_BASE", f"http://127.0.0.1:{server.server_address[1]}"
    )
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-embedding-key")
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", True)
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def test_embed_texts_sync_survives_consecutive_event_loops(embeddings_endpoint):
    """Two sync embeds in a row must both succeed.

    Each ``embed_texts_sync`` call owns an ``asyncio.run`` loop that closes on
    return, which is exactly what one Celery task invocation does. A client
    cached across those loops fails the second call with "Event loop is
    closed".
    """
    first = embed_texts_sync(["first batch"])
    second = embed_texts_sync(["second batch"])

    assert len(first[0]) == EMBEDDING_DIM
    assert len(second[0]) == EMBEDDING_DIM


def _create_user(db) -> User:
    user = User(
        email="chat-memory-loop@example.com",
        supabase_user_id="chat-memory-loop-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _message(role: MessageRole, content: str) -> dict:
    return ChatMessage(role=role, content=content, timestamp=ASKED_AT).to_dict()


def _create_session_record(db, user: User, history: list[dict]) -> ChatSessionRecord:
    record = ChatSessionRecord(
        session_id=SESSION_ID,
        user_id=user.id,
        context_json={
            "session_id": SESSION_ID,
            "user_id": user.id,
            "current_position": None,
            "conversation_history": history,
            "skill_level": "intermediate",
            "focus_areas": [],
            "recent_topics": [],
        },
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def test_task_second_invocation_embeds_the_next_exchange(
    db, embeddings_endpoint, monkeypatch
):
    """The debounced re-run of the task must embed, not fail on a closed loop.

    Mirrors production: run 1 embeds the first exchange, the player replies
    again, run 2 (a later Celery invocation, i.e. a new event loop) must embed
    the new exchange.
    """
    monkeypatch.setattr(
        "app.tasks.chat_memory_tasks.SessionLocal",
        sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False),
    )
    # Start from no cached client at all, so run 1 creates one on its own loop
    # and run 2 is the invocation that would reuse it. The fix removed this
    # module-level cache, hence raising=False.
    monkeypatch.setattr(
        "app.services.coaching.embedding_service._http_client", None, raising=False
    )

    user = _create_user(db)
    record = _create_session_record(
        db,
        user,
        [
            _message(MessageRole.ASSISTANT, "What would you like to work on?"),
            _message(MessageRole.USER, "I keep losing pieces in the middlegame."),
            _message(MessageRole.ASSISTANT, "Scan for undefended pieces every move."),
        ],
    )

    first = extract_chat_memories_task.run(user.id, SESSION_ID)
    assert first["status"] == "success", first
    assert first["embedded_count"] == 1

    # A new coaching exchange lands before the next debounced run.
    payload = dict(record.context_json)
    payload["conversation_history"] = payload["conversation_history"] + [
        _message(MessageRole.USER, "How do I practise that?"),
        _message(MessageRole.ASSISTANT, "Play ten blunder-check puzzles daily."),
    ]
    record.context_json = payload
    db.commit()

    second = extract_chat_memories_task.run(user.id, SESSION_ID)

    # Pre-fix: {'status': 'failed', 'embedded_count': 0, 'skipped_count': 0,
    #           'reason': 'Event loop is closed', ...}
    assert second["status"] == "success", second
    assert second["embedded_count"] == 1
    assert "reason" not in second

    memories = (
        db.query(SemanticMemory).filter(SemanticMemory.content_type == "coaching").all()
    )
    assert len(memories) == 2
