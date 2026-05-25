# ChessIQ Engineering Process — Grep-Review Loop

The end-to-end engineering cycle for every feature, fix, or refactor in this repository.
Every task follows this loop — no exceptions.

---

## The Core Cycle

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   PLAN ──► IMPLEMENT ──► GREP REVIEW ──► REFACTOR           │
│     ▲                         │              │              │
│     │           ┌─── issues ──┘              │              │
│     │           ▼                            ▼              │
│     │      (loop until                    TEST              │
│     │       all checks                     │               │
│     │         pass)              ┌── fail ──┘               │
│     │                            ▼                          │
│     └──────────────────── FINAL REVIEW ──► MERGE            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Each phase has a clear entry condition, a concrete exit condition, and defined responsibilities per agent type.

---

## Phase 1: PLAN

**Entry:** Task arrives (issue, PR, or direct request).  
**Exit:** Scope is locked — files to touch are identified, no new files created yet.

### Steps

1. **Read context** — check `AGENTS.md`, `docs/README.md`, and the relevant `docs/architecture/` document.
2. **Reference check** — run inspection commands from `workflows/reference-context-usage.md` for the domain.
3. **Duplicate check** — grep for existing implementations before writing any code:
   ```bash
   # Does this service already exist?
   rg "<function_name>" backend/app/services/ --type py
   rg "<hook_name>"     frontend/src/hooks/   --type ts
   ```
4. **Define scope** — list exactly which files will be created or modified. If the scope exceeds 5 files or 200 lines, split into smaller tasks.
5. **Architecture fit** — confirm the change fits the layered model:
   - New route → goes in `backend/app/api/`
   - New logic → goes in `backend/app/services/`
   - New task → goes in `backend/app/tasks/`
   - New UI → goes in `frontend/src/components/`
   - New data fetch → goes in `frontend/src/hooks/`

### Per-Agent Guidance

| Agent | Plan behaviour |
|-------|---------------|
| **Cursor** | Read `AGENTS.md` first. Use Grep/Glob to confirm no existing implementation. |
| **GPT-5.5 (backend)** | Run A1–A3 checks mentally before writing. Confirm service-layer placement. |
| **Opus (frontend)** | Review `frontend/src/lib/` and `frontend/src/hooks/` before adding new files. |

---

## Phase 2: IMPLEMENT

**Entry:** Plan is approved / scope is locked.  
**Exit:** Code compiles and passes basic smoke test.

### Rules

- **One responsibility per file.** If a file needs to do two things, create two files.
- **No inline logic in routes or pages.** Routes call services. Pages compose components.
- **Reference first.** If you're calling Stockfish, Supabase, or an LLM, check `reference/<domain>/` for the correct API surface.
- **Small commits.** Commit after each logical unit (router added, service method added, component created). Do not commit a 500-line change in one shot.

### Per-Agent Guidance

| Agent | Implement behaviour |
|-------|-------------------|
| **Cursor** | Read existing files before editing. Use the correct lib factory (e.g. `createClient()` not inline Supabase). |
| **GPT-5.5 (backend)** | Emit service methods first, then route handlers. Use `get_db` Depends pattern. |
| **Opus (frontend)** | Build component → extract custom hook → wire to page. Never skip the hook layer. |

---

## Phase 3: GREP REVIEW

**Entry:** Implementation complete — code compiles.  
**Exit:** All blocking checks return exit code 0.

This is the automated inspection gate. Run scripts from `scripts/review-loops/`.

### Quick Check (before every commit)

```powershell
.\scripts\review-loops\check-architecture.ps1
.\scripts\review-loops\check-security.ps1
```

Both must pass (exit 0) before pushing.

### Full Suite (before every PR)

```powershell
.\scripts\review-loops\full-review.ps1
```

Expected output: `RESULT: READY TO MERGE ✓`

### Triage Protocol

For each finding, classify immediately:

| Classification | Criteria | Action |
|---------------|---------|--------|
| **Real violation** | Code breaks an architecture rule with no justification | Fix before continuing |
| **Acceptable exception** | Rule is intentionally bypassed (e.g. `engine_pool.py` calling `popen_uci`) | Add `# grep-exempt: <reason>` to the source line |
| **False positive** | grep pattern is too broad — matched unrelated code | Document it, do not add grep-exempt |

### Grep Review Loop

```
Run full-review.ps1
       │
       ▼
   All pass? ──YES──► proceed to REFACTOR phase
       │
      NO
       │
       ▼
  Triage findings
       │
       ├─ Real violation ──► Fix code ──► Re-run affected check
       │
       ├─ Acceptable     ──► Add grep-exempt comment ──► Re-run check
       │
       └─ False positive ──► Document, skip
       │
       ▼
   Re-run full-review.ps1  (back to top)
```

---

## Phase 4: REFACTOR

**Entry:** All blocking grep checks pass.  
**Exit:** Code meets naming, size, and structure standards.

### Refactor Checklist

- [ ] All Python files under 300 lines (`check-sizes.ps1 -Series F` returns no hard failures)
- [ ] All React components under 200 lines
- [ ] Naming follows conventions (`check-naming.ps1` returns ≤ N warnings as at start of task)
- [ ] No `TODO: fix later` comments in new code
- [ ] No commented-out debug code (`console.log`, `print()`, `breakpoint()`)
- [ ] Imports are clean — no unused imports

### Refactor Loop

See `skills/refactor-loop.md` for the iterative convergence protocol.

---

## Phase 5: TEST

**Entry:** Refactor complete.  
**Exit:** Relevant tests pass, no new test failures introduced.

### Minimum Test Coverage

| Layer | Minimum |
|-------|---------|
| New service method | 1 happy-path + 1 error-path pytest |
| New API route | 1 integration test via `TestClient` |
| New React hook | 1 unit test via `@testing-library/react` |
| New React component | Smoke test (renders without crashing) |

### Test Run Commands

```bash
# Backend
cd backend && pytest tests/ -x -q

# Frontend
cd frontend && npm test -- --watchAll=false
```

---

## Phase 6: FINAL REVIEW

**Entry:** All tests pass.  
**Exit:** PR is opened, description written, merged.

### Final Review Checklist

- [ ] `full-review.ps1` produces `READY TO MERGE ✓`
- [ ] PR description references the task/issue
- [ ] PR description includes: _what changed_, _why_, _how to test_
- [ ] No `.env` files staged (`git status` confirms)
- [ ] Commit messages are meaningful (no "fix", "wip", "update")
- [ ] Branch name follows `feat/`, `fix/`, `chore/` convention
- [ ] PR scope: ≤ 400 lines changed (if larger, split the PR)

### Merge Rules

Per `AGENTS.md`: PRs merge automatically without waiting for approval unless explicitly told otherwise.

---

## Review Cycles

### Continuous Review Cycle (every PR)

```
Phases 1–6 above, always in sequence.
```

### Architecture Health Cycle (monthly or after major feature)

```
1. Run full-review.ps1 on entire codebase
2. Run skills/architecture-review.md inspection
3. File architectural debt issues
4. Prioritise top-3 issues for next sprint
```

### Cleanup Loop (after every sprint)

```
1. Run check-sizes.ps1 — identify files approaching limits
2. Run check-duplicates.ps1 — find emerging duplication
3. File cleanup tasks before they become violations
4. Execute skills/code-cleanup.md for each task
```

### Drift Detection Loop (quarterly)

```
1. Compare current architecture against docs/architecture/
2. Run skills/architecture-review.md — full drift audit
3. Update architecture docs if implementation intentionally diverged
4. File refactor tasks if implementation unintentionally diverged
```

---

## Agent-Specific Process Guides

### Cursor Agents

Cursor has full tool access (read, write, shell, grep). Use the full loop.

```
1. Read AGENTS.md + relevant docs  (5 min)
2. Grep for existing implementations  (2 min)
3. Implement in small commits  (variable)
4. .\scripts\review-loops\full-review.ps1  (10 s)
5. Fix violations, re-run  (variable)
6. Run tests  (variable)
7. Open PR with full description
```

### GPT-5.5 Backend Workflows

GPT-5.5 (Codex) excels at structured, algorithmic backend code. Optimise for it:

```
1. Provide full file contents as context (not snippets)
2. Specify exact service method signatures before asking for implementation
3. After implementation: run check-architecture.ps1 and check-duplicates.ps1
4. Use GPT-5.5 for: route handlers, service methods, Celery tasks, SQL queries
5. Do NOT use GPT-5.5 for: architectural decisions, refactor strategy, naming
```

Prompt template for GPT-5.5:
```
Context: [paste relevant service file]
Reference: [paste relevant section from reference/<domain>/README.md]
Task: implement <method_name> in <service_file> following the existing pattern above.
Constraints:
- Must not duplicate <existing_function> in <other_file>
- Must use get_db Depends pattern for DB access
- Must not call Stockfish/LLM directly (use existing service wrapper)
```

### Opus Frontend Workflows

Claude Opus excels at reasoning, architecture, and complex UI logic. Optimise for it:

```
1. Provide component tree context (which components exist, how they relate)
2. Specify the data shape (TypeScript interface) before asking for component
3. After implementation: run check-architecture.ps1 and check-sizes.ps1
4. Use Opus for: complex components, custom hooks, layout decisions, accessibility
5. Do NOT use Opus for: boilerplate data fetching, simple utility functions
```

Prompt template for Opus:
```
Context: [paste relevant page and existing components]
Data shape: [paste TypeScript interface]
Task: build <ComponentName> that [description].
Constraints:
- Must not call axios/fetch directly — use existing useQuery hook or add to frontend/src/hooks/
- Must not import Supabase client directly — use existing lib/supabase/client.ts
- Lines budget: 150 lines maximum
- Extract any sub-component > 50 lines into a separate file
```

---

## Workflow Invocation Templates

Use these templates in agent prompts to invoke each phase:

### Invoke PLAN phase
```
Run the PLAN phase for: [task description]
Check: does this already exist in backend/app/services/ or frontend/src/hooks/?
Define scope: list files to create/modify.
Confirm architecture placement.
```

### Invoke GREP REVIEW phase
```
Run the full grep-loop review on branch: [branch-name]
Execute: .\scripts\review-loops\full-review.ps1
Triage all findings.
Fix all real violations.
Re-run until READY TO MERGE.
```

### Invoke REFACTOR phase
```
Run the refactor loop on the implementation in: [file paths]
Apply skills/refactor-loop.md convergence protocol.
Confirm all files are within size limits.
Clean all warnings from check-naming.ps1.
```

### Invoke Architecture Health Cycle
```
Run skills/architecture-review.md on the full codebase.
Identify top-3 architectural debt items.
Produce a findings report in the format from workflows/grep-review-workflow.md.
```
