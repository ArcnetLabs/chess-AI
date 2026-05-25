# Prompt: Backend Implementation

Use when adding a FastAPI route, service function, or Celery task to ChessIQ.

---

## Template

```
We are adding a backend feature to ChessIQ.

Feature: <describe the feature in one sentence>

STEP 1 — Inspect existing code before writing anything new:
1. Search `backend/app/services/` for functions related to <domain keyword>:
   rg "def.*<keyword>" backend/app/services/ --type py
2. Search `backend/app/api/` for related routes:
   rg "@router.*<keyword>\|def <keyword>" backend/app/api/ --type py
3. Search `backend/app/tasks/` for related Celery tasks:
   rg "def.*<keyword>" backend/app/tasks/ --type py
4. Report what you found. Do not create a new service if an existing one can be extended.

STEP 2 — Inspect the reference source for any external library this touches:
<Choose the relevant check below>

For Stockfish:
  rg "def analyze\|class.*Engine\|batch" reference/stockfish/ --type py
  Then verify: rg "def analyze\|get_engine_pool" backend/app/services/engine/ --type py

For python-chess (PGN/FEN):
  rg "read_game\|mainline_moves\|class Board" reference/chess/ --type py

For Celery tasks:
  rg "self.retry\|max_retries\|chain\|chord" reference/queue-workers/ --type py

For AI/LLM:
  rg "def chat\|def generate\|async.*stream" reference/ai-chat/ --type py
  Then verify: rg "def.*generate\|def.*stream" backend/app/services/chat/ --type py

STEP 3 — Implement using the service-layer pattern:
Architecture:
- New logic → `backend/app/services/<domain>/<module>.py`
- Background work → `backend/app/tasks/analysis_tasks.py` (add to existing file, not new file)
- API endpoint → `backend/app/api/<module>.py`
- Route decides WHAT. Service handles HOW. Task is a service wrapper.

STEP 4 — Verify before committing:
Run: python -m mypy app/ --ignore-missing-imports
Run: pytest tests/ -v -m "not slow"
Run: rg "SimpleEngine|popen_uci" backend/app/api/ backend/app/tasks/ --type py (should return 0)

STEP 5 — Summary:
State: which reference files you searched, which existing services you extended or verified,
and which new files were created with justification.

Files to touch:
<list specific files — not "various files">

Do not touch:
<list files to leave unchanged>
```

---

## Pre-Implementation Checklist

Before pasting the prompt above, verify:

- [ ] You know the exact `backend/app/services/<domain>/` module to extend or create.
- [ ] You know whether a Celery task is needed (async background) or not (sync sub-200ms).
- [ ] You know the DB schema impact (none / new column / new table / migration needed).
- [ ] The `reference/` folder for the relevant library is populated — or the implementation avoids guessing.

## Post-Implementation Checklist

- [ ] `mypy` passes.
- [ ] `pytest` passes.
- [ ] Architecture grep checks from `.cursor/rules/review-loops.mdc` pass.
- [ ] No hardcoded Stockfish depths or LLM token limits — these live in config/service constants.
