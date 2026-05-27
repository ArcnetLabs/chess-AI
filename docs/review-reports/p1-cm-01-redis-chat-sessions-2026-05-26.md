# P1-CM-01 — Redis Chat Session Store

**Date:** 2026-05-26  
**Agent:** Infrastructure / Performance  
**Branch:** `feature/infra-redis-chat-sessions`  
**Scope:** Replace in-memory `ChessCoach.sessions` dict with Redis-backed persistence

---

## Summary

Chat sessions are now stored in Redis via `ChatSessionStore`, enabling multi-worker FastAPI deployments to share session state. When Redis is unavailable (local dev), the store falls back to an in-process dict — matching the `pattern_tasks` debounce pattern.

**No Alembic migration required.** Sessions are ephemeral cache data, not relational rows.

---

## Redis key / TTL design

| Item | Value |
|------|-------|
| Key prefix | `chat:session` |
| Full key | `chat:session:{session_id}` |
| TTL | 86400s (24h) default |
| Config | `CHAT_SESSION_TTL_SECONDS` env / `settings.CHAT_SESSION_TTL_SECONDS` |
| Write | `SETEX key ttl json_payload` on every save (refreshes TTL) |
| Read | `GET chat:session:{session_id}` |
| Delete | `DEL chat:session:{session_id}` |
| Health count | `SCAN` with match `chat:session:*` |

### Payload

JSON serialization of `ChatContext.to_dict()` — includes `conversation_history` (last 20 messages enforced by `ChatContext.add_message`), `current_position`, `user_id`, `skill_level`, `focus_areas`, `recent_topics`.

---

## Fallback behavior

| Condition | Behavior |
|-----------|----------|
| `redis_client is None` (dev, Redis unreachable) | All CRUD uses in-process `_memory` dict |
| Redis `GET`/`SETEX`/`DELETE` raises | Log warning; read/write/delete falls back to `_memory` for that operation |
| Staging/production, Redis unreachable at startup | App fails fast (existing `database.py` policy) — sessions require Redis in deployed envs |

**Note:** In-memory fallback is per-process only. Multi-worker dev without Redis will still have split-brain sessions — acceptable for local dev; staging/production must have Redis.

---

## Files changed

| File | Change |
|------|--------|
| `backend/app/services/chat/session_store.py` | **New** — serialize/deserialize, Redis CRUD, fallback |
| `backend/app/services/chat/chess_coach.py` | Use `ChatSessionStore`; save after each message |
| `backend/app/services/chat/__init__.py` | Add `session_id` to `ChatResponse` |
| `backend/app/api/chat.py` | Fix session lookup bug; health uses `active_session_count()` |
| `backend/app/core/config.py` | Add `CHAT_SESSION_TTL_SECONDS` |
| `backend/tests/test_chat_session_store.py` | **New** — 16 tests |

---

## Architecture grep (pre-PR)

| Check | Result |
|-------|--------|
| Stockfish outside pool in api/tasks | ✅ Clean |
| LLM calls outside chess_coach in api | ✅ Clean |
| `self.sessions` in chat service | ✅ Removed |
| Alembic migration | ✅ Not required |

---

## Test results

```
pytest tests/test_chat_session_store.py tests/test_pattern_tasks.py -v --no-cov
21 passed
```

Coverage gate not run on isolated file (full suite recommended in CI).

---

## OPS-01 — Alembic reminder (unrelated to this PR)

Staging and production Postgres must run:

```bash
cd backend && alembic upgrade head
```

to apply migrations **0006** (pattern schema) and **0007** (profile schema) if not already applied. This PR does not add migration **0008** or any schema change.

---

## Follow-ups (out of scope)

- P1-CM-02: Coach context assembly (profile + patterns)
- Per-user session ownership checks on chat routes
- Persist sessions to Postgres for long-term memory (architecture doc)
