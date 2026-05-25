# Prompt: Refactoring

Use when cleaning up existing code without changing user-facing behaviour. Always a separate PR from the feature that produced the messy code.

---

## Template

```
Run a focused refactoring pass on ChessIQ.

Target area: <describe what to clean up — e.g. "game analysis service", "auth flow pages">

STEP 1 — Audit the target area:
1. List all files in the target area:
   Get-ChildItem <directory> -Recurse -Filter "*.py" | Select Name
   or: Get-ChildItem <directory> -Recurse -Filter "*.ts" | Select Name
2. For each file, identify:
   - Duplicated logic (same function body / similar names)
   - Logic that belongs in the service layer but is in a route or component
   - Hardcoded values that should be constants or config
   - Dead code (functions that are never called)

STEP 2 — Run the duplication grep suite:
Backend:
  rg "def analyze_\|def fetch_\|def generate_" backend/app/ --type py
  rg "SimpleEngine\|popen_uci" backend/app/api/ backend/app/tasks/ --type py
  rg "openai\.\|ollama\." backend/app/api/ --type py

Frontend:
  rg "axios\.(get|post|put|delete)" frontend/src/components/ frontend/src/pages/ --type ts
  rg "createBrowserClient\|createServerClient" frontend/src/ --type ts -l
  rg "supabase\.auth\." frontend/src/pages/ --type ts

Report each finding before touching any file.

STEP 3 — Propose the refactoring plan:
For each finding:
- Name the duplication clearly
- State which file should be the single source of truth
- State which files should be updated to use that source
- Estimate the diff size (keep it under 200 lines)

Wait for confirmation on the plan before implementing.

STEP 4 — Implement:
- One concern at a time. Do not mix multiple refactors in one commit.
- Keep domain policy in callers. Move mechanics to services.
- Do not rename things gratuitously — renaming makes PRs hard to review.
- Do not change user-facing behaviour.

STEP 5 — Verify:
Run: python -m mypy app/ --ignore-missing-imports (backend)
Run: cd frontend && npm run type-check (frontend)
Run: pytest tests/ -v -m "not slow" (backend)

Confirm: user-facing behaviour is identical before and after.
```

---

## Scope Guard

**This prompt is for mechanics refactoring only.** Do not use it to:
- Change product behaviour or add features.
- Rename everything for aesthetic reasons.
- Restructure the entire codebase.
- Mix in "while I was here" improvements.

If you catch yourself doing any of the above, stop and open a separate PR.

---

## Common ChessIQ Refactoring Targets

| Target | Typical finding | Correct resolution |
|--------|----------------|-------------------|
| Route handlers | Inline analysis logic | Extract to `services/analysis/` |
| Pages with `getServerSideProps` | Direct `supabase.auth.getUser()` | Replace with `withAuth` HOC |
| Celery tasks | Inline business logic | Extract to service function, task calls service |
| Multiple similar API hooks | Duplicate `useQuery` setup | Compose from common base hook |
| Hardcoded Stockfish depth values | `depth=15` in 4 different files | Single constant in `engine_pool.py` |
