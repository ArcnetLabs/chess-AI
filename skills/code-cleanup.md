# Skill: Code Cleanup

**When to use:** After a feature works and is merged. Run a focused cleanup pass to extract duplicate mechanics into the service layer. This is always a separate PR from the feature itself.

---

## When NOT to Use

- Before the feature works (cleanup during development derails delivery).
- As an excuse to rename everything or restructure unrelated code.
- When the feature touched a single file and there is no obvious duplication.

---

## Cleanup Prompt Template

```
The feature is working. Run a code-structure cleanup pass on the files it touched.

Goal:
- Find duplicated logic, repeated API calls, repeated parsing, or repeated Stockfish access.
- Extract repeated mechanics into the existing service layer (do not create new service files unless truly necessary).
- Keep domain policy in routes/components, mechanics in services.
- Do not change user-facing behaviour.
- Keep the diff small and focused.

Files to inspect:
[list the files touched by the feature]

Process:
1. Read each file.
2. Identify duplicated patterns and name them clearly.
3. Show the extraction plan (what moves where).
4. Implement it.
5. Run npm run type-check (frontend) or mypy (backend).
6. Summarize exactly what got simpler.
```

---

## ChessIQ-Specific Duplication Patterns to Look For

### Backend

```bash
# Multiple copies of game-fetching logic
rg "chesscom_api\|chess\.com" backend/app/ --type py -l

# Stockfish called outside the engine pool
rg "SimpleEngine\|popen_uci\|chess\.engine" backend/app/ --type py

# Repeated Celery task patterns (delay + signature duplication)
rg "\.delay\(" backend/app/api/ --type py

# Direct SQLAlchemy queries duplicated across routes
rg "db\.query\|db\.execute" backend/app/api/ --type py

# Repeated error-handling boilerplate
rg "except Exception" backend/app/api/ --type py
```

### Frontend

```bash
# Direct axios calls outside api.ts
rg "axios\.\(get\|post\|put\|delete\)" frontend/src/components/ frontend/src/pages/ --type ts

# Repeated loading/error state patterns in components
rg "const \[loading, setLoading\]" frontend/src/pages/ --type ts

# Repeated Supabase client instantiation
rg "createBrowserClient\|createServerClient" frontend/src/ --type ts
# (should only appear in src/lib/supabase/)

# Repeated auth checks in getServerSideProps
rg "supabase\.auth\.getUser" frontend/src/pages/ --type ts
# (should only appear via withAuth helper)
```

---

## Service Layer Extraction Rules

| What was duplicated | Move it to |
|---------------------|-----------|
| Game fetching / Chess.com API | `backend/app/services/integration/chesscom_api.py` |
| Stockfish analysis calls | `backend/app/services/analysis/unified_analyzer.py` |
| Pattern scoring | `backend/app/services/coaching/recommendation_engine.py` |
| LLM/chat context assembly | `backend/app/services/chat/chess_coach.py` |
| Auth validation (backend) | `backend/app/core/database.py` or a new `auth.py` utility |
| API call wrappers (frontend) | `frontend/src/lib/api.ts` |
| Supabase data hooks | `frontend/src/services/` or `frontend/src/hooks/` |

---

## Verification Checklist

- [ ] User-facing behaviour unchanged (manual smoke test).
- [ ] Calling files became shorter and simpler.
- [ ] No new service files created without justification.
- [ ] `npm run type-check` passes (frontend).
- [ ] Diff is scoped to the feature's file set.
- [ ] No console.log / print debug statements introduced.
