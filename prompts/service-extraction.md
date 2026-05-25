# Prompt: Service Extraction

Use when a feature is working but its logic is scattered across routes, tasks, or components and needs to be consolidated into a proper service-layer module.

---

## Template

```
Extract duplicated logic into a ChessIQ service module.

Duplication to address: <describe the duplicated logic — e.g. "PGN parsing appears in 3 files">

STEP 1 — Locate all instances of the duplication:
rg "<keyword>" backend/app/ --type py -n
or: rg "<keyword>" frontend/src/ --type ts -n
List every file and line number where this logic appears.

STEP 2 — Identify the canonical service location:
Backend service map:
  backend/app/services/analysis/   ← game analysis, position evaluation
  backend/app/services/chat/        ← LLM, coaching responses
  backend/app/services/coaching/    ← pattern recognition, recommendations
  backend/app/services/engine/      ← Stockfish engine pool
  backend/app/services/integration/ ← Chess.com API, external data
  backend/app/services/moves/       ← move recommendations

Frontend abstraction map:
  frontend/src/lib/api.ts           ← all API client functions
  frontend/src/hooks/               ← all React Query hooks
  frontend/src/lib/supabase/        ← Supabase client factories (do not add to these)
  frontend/src/lib/auth/            ← auth helpers (do not add to these)

Which service module should own this logic?
If no existing module fits, propose the new file path with justification.

STEP 3 — Define the extracted function signature:
Before writing code, show the proposed function:
  [language]
  # Backend
  async def <function_name>(args, db: AsyncSession) -> ReturnType:
      """<what it does, inputs, outputs>"""
  
  // Frontend
  export async function <functionName>(args: ArgType): Promise<ReturnType>

Get confirmation on the signature before implementation.

STEP 4 — Implement the extraction:
1. Write the service function (or extend the existing service class).
2. Update each caller to use the new function.
3. Remove the duplicated code from each caller.
4. Keep the callers' domain policy intact — only move mechanics.

STEP 5 — Verify the extraction:
- Run type-check / mypy.
- Run tests.
- Confirm callers are simpler (fewer lines) after the extraction.
- Confirm the extracted function is the single source of truth:
  rg "<old duplicated pattern>" <caller directories> --type <py|ts>
  (should return 0 results)
```

---

## Extraction Decision Matrix

| Logic type | Extract to | Keep in |
|------------|-----------|---------|
| External API calls | service module | — |
| Data transformation / parsing | service module | — |
| DB queries | service module | — |
| Business rules ("is this a blunder?") | service module | — |
| HTTP response formatting | — | route handler |
| UI rendering decisions | — | component |
| Which service to call | — | route handler / component |
| "Should we retry?" | — | Celery task |

---

## ChessIQ-Specific Extraction Patterns

### Scattered game fetching → `chesscom_api.py`

```python
# Before: identical Chess.com fetch in 3 routes
# After: single function
async def fetch_games(username: str, max_games: int = 50) -> list[GameData]:
    """Fetch and normalise games from Chess.com API."""
```

### Scattered board walking → `unified_analyzer.py`

```python
# Before: manual board.push(move) loops in 3 services
# After: generator
def walk_positions(game: chess.pgn.Game) -> Generator[chess.Board, None, None]:
    """Iterate over all positions in a game."""
```

### Scattered API calls → `frontend/src/lib/api.ts`

```typescript
// Before: axios.get('/api/v1/users/${id}/games') in 3 components
// After: single function
export const gameApi = {
  getByUsername: (username: string) =>
    apiClient.get<GameData[]>(`/users/${username}/games`).then(r => r.data)
}
```
