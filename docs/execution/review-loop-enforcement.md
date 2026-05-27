# ChessIQ Review Loop Enforcement

**Date:** 2026-05-26  
**Purpose:** Mandatory quality gates for feature execution — grep, architecture, duplication, performance, service layer  
**Companion:** [`parallel-development-workflows.md`](./parallel-development-workflows.md), [`../../workflows/grep-review-workflow.md`](../../workflows/grep-review-workflow.md)

---

## Philosophy

Feature velocity is allowed **only** when invariants hold. Remediation established canonical paths; review loops prevent regression into duplicate analyzers, unauthenticated routes, and monolithic pages.

**Rule:** No PR merges to `staging` without A+D grep pass. No `staging` → `main` without full A–E suite.

---

## Review tiers

| Tier | When | Scope | Blocking? |
|------|------|-------|-----------|
| **R0 — Author self-check** | Before push | Type-check, pytest, A+D grep | Yes |
| **R1 — PR gate** | PR to staging | R0 + PR scope review | Yes |
| **R2 — Phase gate** | Phase completion | Full A–E + smoke | Yes |
| **R3 — Release gate** | staging → main | R2 + production smoke | Yes |
| **R4 — Post-feature cleanup** | After phase merge | Duplication pass, separate PR | Recommended |

---

## 1. Post-feature grep reviews

### R1 — Every PR (required)

Run from repo root (see `skills/grep-loop-review.md` for PowerShell alternatives when `rg` unavailable):

```bash
# A1 — Stockfish outside pool
rg "SimpleEngine|popen_uci|subprocess.*stockfish" backend/app/api/ backend/app/tasks/

# A2 — LLM outside coach
rg "openai\.|anthropic\.|ollama\." backend/app/api/

# A3 — DB session in routes
rg "from app.core.database import SessionLocal" backend/app/api/

# A4 — Frontend HTTP bypass
rg "axios\.(get|post|put|delete)" frontend/src/components/ frontend/src/pages/

# A5 — Service role leak
rg "service_role|SERVICE_ROLE" frontend/src/

# D1 — Auth bypass in pages (except auth/*)
rg "supabase\.auth\." frontend/src/pages/ --glob "!**/auth/**"
```

**Pass criteria:** Zero matches, or explicit `# grep-exempt:` with architect approval in PR.

### R2 — Phase gate (full A–E)

Add to R1:

```bash
# B — Duplication
rg "def analyze_" backend/app/
rg "def fetch_games" backend/app/
rg "class.*Analyzer" backend/app/services/

# C — Frontend structure
rg "useQuery|useMutation" frontend/src/pages/   # should be minimal; prefer hooks/
wc -l frontend/src/pages/*.tsx                    # pages should stay thin

# E — Stray scripts
rg "create_all" backend/app/
```

Produce a findings report in `docs/review-reports/` per `docs/review-reports/README.md`.

---

## 2. Architecture validation

### Canonical access points (must not regress)

| Concern | Canonical path | Violation grep |
|---------|----------------|----------------|
| Stockfish | `services/engine/engine_pool.py` | A1 above |
| LLM / coach | `services/chat/chess_coach.py` | A2 above |
| Game analysis | `services/analysis/analysis_service.py` + `unified_analyzer.py` | Duplicate `def analyze_` |
| Auth | Supabase JWT → `middleware/auth_middleware.py` | Unguarded mutating routes |
| Frontend API | `lib/api.ts` | A4 above |
| Chat HTTP | `lib/api.ts` → `chatApi` | `fetch(` in chat components |

### Route thinness check

For each new/modified route in `backend/app/api/`:

- [ ] Input validation only (Pydantic / path params)
- [ ] Single service call (or orchestration ≤ 10 lines)
- [ ] No Stockfish, no LLM, no raw SQL
- [ ] `Depends(get_current_user)` on mutating endpoints

### Frontend layer check

For each new/modified page:

- [ ] Page ≤ ~100 lines
- [ ] Data fetching in `hooks/`
- [ ] UI in `components/` or `features/`
- [ ] No inline `setInterval` polling (use hooks + services)

### Documentation sync

When architecture changes:

- [ ] Update relevant doc in `docs/architecture/`
- [ ] Update `repository-invariants.md` if rule changed
- [ ] Add entry to phase checklist in execution roadmap

---

## 3. Duplication checks

### Before adding any function

```bash
rg "def <function_name>" backend/app/services/
rg "<function_name>" frontend/src/lib/ frontend/src/hooks/
```

Extend existing implementation — do not parallel.

### Known consolidation targets (do not recreate)

| Deleted / canonical | Do not recreate |
|---------------------|-----------------|
| `core/ai_client.py` | Use `integration/ai_client.py` |
| `chess_analyzer.py`, `chess_analysis.py` | Use `unified_analyzer.py` |
| `analysis_stockfish.py` | Use `analysis.py` + service layer |
| Inline dashboard polling | Use `analysisPollingService.ts` + hooks |
| Raw chat `fetch` | Use `api.chat.*` |

### Post-feature cleanup PR (R4)

After a phase merges, run:

```markdown
Prompt: "Phase [N] merged. Duplication cleanup pass only.
Find parallel logic introduced during the phase.
Extract into existing service layer. No behavior change. ≤ 200 lines."
```

Separate PR — never mixed with feature logic.

---

## 4. Performance checks

### Backend

| Check | When | Action |
|-------|------|--------|
| Celery task duration | New analysis/pattern tasks | Log timing; cap batch size |
| Engine pool exhaustion | High concurrency changes | Review `engine_pool.py` settings with Infra |
| N+1 queries | New list endpoints | SQLAlchemy eager load / joinedload |
| Redis TTL | New cache keys | Document TTL in service module |

**Infra agent** runs `backend/scripts/verify_celery_worker_env.py` before worker config PRs.

### Frontend

| Check | When | Action |
|-------|------|--------|
| React Query `staleTime` | New hooks | Avoid refetch storms |
| Polling intervals | Any status polling | Prefer SSE when available (Phase 2) |
| Bundle size | New pages | Lazy-load heavy chart routes if needed |
| Re-render hotspots | Large lists | Memoize game list items |

### Database

| Check | When | Owner |
|-------|------|-------|
| Index on foreign keys | New tables | Infra migration |
| JSONB query patterns | Profile/pattern storage | EXPLAIN on staging |
| Migration lock time | Large backfills | Batch in Celery, not migration |

---

## 5. Service-layer checks

### Backend service rules

```
Route → Service → (Task → Service) → Model/External API
```

- [ ] Business logic lives in `services/`, not `api/` or `tasks/`
- [ ] Tasks call services — no inline analysis logic in `tasks/`
- [ ] External APIs wrapped (`chesscom_api`, `ai_client`) — not called from routes
- [ ] Exceptions mapped to HTTP in route layer only

### Frontend service rules

```
Page → Feature → Hook → lib/api.ts
```

- [ ] `services/` holds non-React mechanics (polling timers, chat session id)
- [ ] Server state in React Query hooks, not Zustand
- [ ] Zustand for UI only (chat open/minimize, not game lists)

### Verification commands

```bash
# Backend service layer
cd backend && python -m mypy app/ --ignore-missing-imports

# Frontend types
cd frontend && npm run type-check

# Tests
cd backend && pytest tests/ -q
```

---

## Merge blockers (hard stop)

| Condition | Action |
|-----------|--------|
| A1 Stockfish violation | Block merge; fix or architect exemption |
| A2 LLM in route | Block merge |
| A4 axios in component | Block merge |
| A5 service_role in frontend | Block merge — security incident |
| Unguarded DELETE/POST | Block merge |
| PR > 600 lines without justification | Split PR |
| Migration without downgrade note | Infra must document |
| Phase gate checklist incomplete | Block staging → main |

---

## Review report template

Save to `docs/review-reports/YYYY-MM-DD-<topic>-grep-review.md`:

```markdown
# Grep Review — [topic]

**Date:** YYYY-MM-DD  
**Scope:** [PR # / phase gate]  
**Reviewer:** [agent role]

## Summary
- A-series: PASS / FAIL (N findings)
- D-series: PASS / FAIL
- Duplication: PASS / FAIL
- Service layer: PASS / FAIL

## Findings
| ID | Severity | File:Line | Rule | Action |

## Exemptions
| File | Rule | Justification | Approved by |

## Sign-off
- [ ] Ready for staging merge
- [ ] Ready for main promotion
```

---

## CI integration (target state)

| Check | Status | Location |
|-------|--------|----------|
| pytest | Run on PR | `.github/workflows/` (when configured) |
| frontend type-check | Run on PR | same |
| grep-loop script | Run on PR | `scripts/review-loops/` |
| mypy | Optional on PR | backend |

Until CI is fully wired, **R0 self-check is mandatory** for every agent.

---

## Phase gate sign-off template

Principal Architect confirms at end of each phase:

```markdown
## Phase [N] Gate Sign-off

- [ ] All roadmap units [IDs] merged to staging
- [ ] Full grep A–E: PASS (report link)
- [ ] pytest + type-check: PASS
- [ ] Staging smoke: PASS (URLs, date)
- [ ] Architecture docs updated
- [ ] No open P0 violations from audit
- [ ] Cleanup PR opened or N/A

Approved for staging → main: YES / NO
```

---

## Quick reference card

```
BEFORE PUSH
  □ type-check / pytest
  □ grep A + D
  □ single concern, <400 lines

BEFORE STAGING MERGE
  □ PR scope matches agent role
  □ routes thin, services own logic
  □ no new duplicate functions

BEFORE MAIN RELEASE
  □ full grep A–E report
  □ phase checklist complete
  □ staging smoke passed
```

---

## Related documents

- [`feature-execution-roadmap.md`](./feature-execution-roadmap.md) — phase exit criteria
- [`../../skills/grep-loop-review.md`](../../skills/grep-loop-review.md) — full grep suite
- [`../../.cursor/rules/review-loops.mdc`](../../.cursor/rules/review-loops.mdc) — Cursor rules
- [`../architecture/repository-invariants.md`](../architecture/repository-invariants.md) — authoritative rules
- [`../review-reports/README.md`](../review-reports/README.md) — report rotation
