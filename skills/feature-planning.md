# Skill: Feature Planning

**When to use:** Before implementing any non-trivial feature in ChessIQ. Forces scoped, architecture-aware planning before code is written.

---

## Trigger Conditions

Use this skill when the user says any of: "add X feature", "build X", "implement X", and X touches more than one file or layer.

---

## Planning Protocol

### Step 1 — Locate the existing surface

Before proposing anything new, search the codebase:

```bash
# Find related services
rg "<feature keyword>" backend/app/services/ --type py -l
rg "<feature keyword>" frontend/src/ --type ts -l

# Find related routes
rg "<feature keyword>" backend/app/api/ --type py -l

# Find related components
rg "<feature keyword>" frontend/src/components/ --type ts -l
```

Report what already exists. Do not create a new service if one exists that can be extended.

### Step 2 — Define the minimal scope

Answer these questions before writing a single line of code:

1. **What is the smallest working version?** (one service function + one route/component)
2. **Which existing services will this extend or call?**
3. **Which new files will be created?** (list exact paths)
4. **Which existing files will be modified?** (list exact paths)
5. **What is the DB schema impact?** (new table / column / index / none)
6. **What is the Celery task impact?** (new task / extend existing / none)
7. **What does the frontend need?** (new page / new component / new API call / none)

### Step 3 — Identify risks

- Does this touch the Stockfish engine pool? (Concurrency risk)
- Does this touch the Supabase auth flow? (Session security risk)
- Does this add a new LLM call? (Token cost risk — document expected tokens/request)
- Does this require a DB migration? (Irreversible if data exists)

### Step 4 — Define the PR split

ChessIQ features typically split into:
1. **DB migration PR** (if needed) — Alembic migration only
2. **Backend service PR** — service layer + Celery task
3. **Backend route PR** — FastAPI endpoint wiring
4. **Frontend PR** — page/component + React Query hook

Each PR should be independently reviewable and mergeable.

---

## Output Format

```
## Feature: <name>

### Existing surface found
- <file>: <what's there>

### Minimal scope
- New files: [list]
- Modified files: [list]
- DB impact: [yes/no + description]
- Celery impact: [yes/no + description]

### PR plan
1. PR #1: [title] — [files]
2. PR #2: [title] — [files]

### Risks
- [risk and mitigation]
```

---

## ChessIQ Service Map (quick reference)

| Domain | Service | Location |
|--------|---------|----------|
| Game analysis | `UnifiedAnalyzer` | `backend/app/services/analysis/unified_analyzer.py` |
| Stockfish engine | `EnginePool` | `backend/app/services/engine/engine_pool.py` |
| Chess.com fetching | `ChessComAPI` | `backend/app/services/integration/chesscom_api.py` |
| AI coaching chat | `ChessCoach` | `backend/app/services/chat/chess_coach.py` |
| Move recommendations | `MoveRecommender` | `backend/app/services/moves/move_recommender.py` |
| Pattern recognition | `RecommendationEngine` | `backend/app/services/coaching/recommendation_engine.py` |
| Supabase auth | `createClient` / `createSupabaseServerClient` | `frontend/src/lib/supabase/` |
| Backend API calls | `api` | `frontend/src/lib/api.ts` |
