# Reference: WebSocket / Real-Time Patterns

Source references for real-time features in ChessIQ — live analysis streaming, move-by-move coaching updates, and board state synchronization.

## Current Status

WebSocket features are **not yet implemented** in ChessIQ. This directory is a placeholder for when real-time analysis streaming is added.

## Planned Use Cases

1. **Live game analysis streaming** — user pastes a PGN and sees move-by-move evaluation as Stockfish processes it.
2. **Real-time coaching chat** — streaming LLM responses from the AI coach (token-by-token).
3. **Position evaluation bar** — live centipawn graph updating during analysis.

## Populate This Directory

```bash
# FastAPI WebSocket examples
git clone --depth=1 https://github.com/tiangolo/fastapi reference/websocket-patterns/fastapi-source
# Key file: fastapi/tests/test_tutorial/test_websockets/

# Next.js WebSocket examples
git clone --depth=1 --filter=blob:none --sparse https://github.com/vercel/next.js reference/websocket-patterns/nextjs-ws
cd reference/websocket-patterns/nextjs-ws
git sparse-checkout set examples/with-socket.io
```

## Architecture Notes (for when this is implemented)

### Backend: FastAPI WebSocket + Celery

```python
# Pattern: WebSocket endpoint for live analysis streaming
@router.websocket("/ws/analyze/{game_id}")
async def analyze_stream(websocket: WebSocket, game_id: str):
    await websocket.accept()
    pool = get_engine_pool()
    async for position_result in pool.stream_analysis(game_id):
        await websocket.send_json(position_result.dict())
    await websocket.close()
```

### Backend: LLM Streaming

```python
# Pattern: streaming LLM response via Server-Sent Events or WebSocket
async def stream_coach_response(context: CoachContext):
    async for chunk in chess_coach.stream(context):
        yield chunk  # Server-Sent Events
```

### Frontend: React Query + WebSocket

```typescript
// Pattern: subscribe to analysis progress
function useAnalysisStream(gameId: string) {
  const [results, setResults] = useState<PositionResult[]>([])

  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/ws/analyze/${gameId}`)
    ws.onmessage = (event) => setResults(prev => [...prev, JSON.parse(event.data)])
    return () => ws.close()
  }, [gameId])

  return results
}
```

## Decision Point (before implementing)

Before adding WebSockets, evaluate:
- Is HTTP polling (current approach) fast enough for the use case?
- Does the LLM provider support streaming? (Ollama: yes, most hosted: yes)
- Can Celery progress be polled via `/tasks/{task_id}/status` instead of WebSocket?

WebSockets add complexity. Polling is simpler and adequate for analysis that takes > 5 seconds.

---

## How Agents Should Inspect This Reference

```bash
# Find FastAPI WebSocket examples
rg "WebSocket\|websocket\|accept\(\)" reference/websocket-patterns/fastapi-source/ --type py -l

# Find streaming/generator patterns
rg "async.*generator\|yield\|EventSourceResponse\|StreamingResponse" reference/websocket-patterns/ -l

# Check if WebSocket is already implemented before building
rg "WebSocket\|websocket" backend/app/ --type py -l
rg "WebSocket\|useWebSocket\|new WebSocket" frontend/src/ --type ts -l
```

## Reuse Safeguards — Never Duplicate These

| Pattern | Status | Rule |
|---------|--------|------|
| Analysis polling | `/api/v1/tasks/{id}` — implemented | Use this before building WebSocket |
| HTTP streaming | Not yet implemented | Build once in `chat.py` endpoint, reuse |
| WebSocket connection management | Not yet implemented | One `ConnectionManager` class, not per-endpoint |

```bash
# Verify no ad-hoc WebSocket implementations before adding one:
rg "@router.websocket\|WebSocket\b" backend/app/api/ --type py
# If results appear, extend the existing implementation
```
