# Prompt: WebSocket / Real-Time Integration

Use when adding streaming analysis, live coaching responses, or real-time board updates to ChessIQ.

---

## Decision Gate (run before using this prompt)

**Is WebSocket actually needed?** Answer these questions first:

```
1. Is the operation < 5 seconds?
   → Use synchronous HTTP. Do not use WebSocket.

2. Can Celery task polling (/api/v1/tasks/{id}/status) cover the UX?
   → Use polling. It's already implemented. Do not add WebSocket.

3. Does the user need token-by-token LLM output streaming?
   → Use Server-Sent Events (simpler than WebSocket for one-way streaming).
   → Check reference/websocket-patterns/ for SSE vs WebSocket guidance.

4. Is this genuinely bidirectional real-time? (e.g. multiplayer board sync)
   → WebSocket is appropriate. Proceed with the prompt below.
```

---

## Template

```
We are adding real-time/streaming capability to ChessIQ.

Feature: <describe what needs to be streamed or sent in real-time>
Transport choice and justification: <SSE / WebSocket / polling — and why>

STEP 1 — Inspect what already exists:
1. Check for existing WebSocket or SSE endpoints:
   rg "@router.websocket\|EventSourceResponse\|StreamingResponse" backend/app/api/ --type py
2. Check for existing frontend streaming hooks:
   rg "useWebSocket\|EventSource\|ReadableStream" frontend/src/ --type ts -l
3. Check reference source for the chosen transport:
   rg "WebSocket\|StreamingResponse\|EventSource" reference/websocket-patterns/ -l
Report what you found. Do not create a second streaming endpoint if one exists.

STEP 2 — Inspect reference source for transport patterns:
For SSE (Server-Sent Events):
  rg "EventSourceResponse\|StreamingResponse\|yield" reference/websocket-patterns/ --type py
  Then: from starlette.responses import StreamingResponse  # FastAPI pattern

For WebSocket:
  rg "WebSocket\|websocket.accept\|ConnectionManager" reference/websocket-patterns/ --type py

STEP 3 — Design the implementation:
Backend:
  New endpoint in: backend/app/api/<module>.py
  Streaming logic in: backend/app/services/<domain>/ (not inline in the route)
  One ConnectionManager class if WebSocket (in services/, not inline)

Frontend:
  New hook in: frontend/src/hooks/use<Feature>Stream.ts
  Component receives stream state as props — does not manage connection

STEP 4 — Implement:
- Backend service handles the streaming generator/async generator.
- Route wires the service into the chosen transport.
- Frontend hook encapsulates connection lifecycle (open, message, close, error).
- Component is stateless about the connection.

STEP 5 — Verify:
Run: python -m mypy app/ --ignore-missing-imports
Run: cd frontend && npm run type-check
Verify: only ONE streaming service/endpoint per domain
  rg "@router.websocket\|EventSourceResponse" backend/app/api/ --type py

STEP 6 — Summary:
State: which reference files confirmed the transport API, what new service function was created,
and why polling was insufficient for this use case.
```

---

## ChessIQ Streaming Architecture Guidelines

### LLM Response Streaming (SSE)

```
POST /api/v1/chat/stream
  ↓
chess_coach.py → async_generator (yields token chunks)
  ↓
StreamingResponse(media_type="text/event-stream")
  ↓
Frontend: EventSource hook → chat component
```

### Analysis Progress Streaming (polling first, SSE if needed)

```
Current approach (polling — already implemented):
  POST /api/v1/users/{id}/analyze → { task_id }
  GET  /api/v1/tasks/{task_id}/status → { status, progress, result }
  Frontend polls every 2s until status === "SUCCESS"

Upgrade path (SSE):
  GET /api/v1/tasks/{task_id}/stream → SSE events with progress updates
```

**Do not build WebSocket for analysis progress — polling is adequate.**
