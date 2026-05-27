# P1-CM-02 — Coach context assembly (profile + patterns)

**Date:** 2026-05-26  
**Branch:** `feature/backend-coach-context`  
**Scope:** Backend only — coach context from DB facts

---

## Summary

Adds `assemble_coach_context` to load the latest `PlayerProfile` and top-N `PlayerPattern` rows (severity then confidence, matching profile builder ordering). Wires context into `ChessCoach._handle_general_question` via optional `db` on `process_message`, with `chat.py` passing `get_db`. LLM path uses a system message when `ai_client` is present; otherwise context is appended to the template fallback.

---

## Files changed

| File | Change |
|------|--------|
| `backend/app/services/chat/context_assembler.py` | New — `assemble_coach_context` |
| `backend/app/services/chat/chess_coach.py` | `db` param; general-question context injection |
| `backend/app/api/chat.py` | `Depends(get_db)` on `/message` |
| `backend/tests/test_coach_context.py` | Unit + coach handler tests |

---

## Architecture checks (R1)

| Check | Result |
|-------|--------|
| Stockfish outside pool (api/tasks) | ✅ No new usage |
| LLM inline in api routes | ✅ None |
| `SessionLocal` in api routes | ✅ Uses `get_db` dependency |
| Redis session store unchanged | ✅ Not modified |

---

## Behaviour

- Context is **read-only facts** from SQLAlchemy models — no Stockfish, no invented evals.
- Missing profile: message notes insufficient analyzed games; patterns still listed if present.
- Pattern ranking: `_SEVERITY_RANK` + confidence (same keys as `profile_builder.py`).

---

## Handlers receiving context

| Handler | Context wired |
|---------|----------------|
| `_handle_general_question` | ✅ Yes (minimum per spec) |
| `_handle_analyze_position` | ❌ Stockfish-backed |
| `_handle_explain_move` | ❌ Position-specific |
| `_handle_compare_moves` | ❌ Position-specific |
| `_handle_small_talk` | ❌ No |
| `_handle_unknown` | ❌ No |

---

## Test plan

```bash
cd backend
pytest tests/test_coach_context.py tests/test_chat_session_store.py -q --no-cov
```

---

## Follow-ups (out of scope)

- Wire context into additional intents (pattern questions, small talk personalization).
- Token budget pruning per `MEMORY_RETRIEVAL_CONTEXT_ARCHITECTURE.md` §5.2.
- Pass `db` on `quick-analysis` when authenticated user context is desired.
