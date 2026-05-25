# Multi-Agent Coordination

How to orchestrate multiple AI agents working in parallel on ChessIQ without creating conflicts, duplication, or broken merges.

---

## Core Problem

Multiple agents working on the same repository simultaneously will:
- Create conflicting edits to shared files (`api.ts`, `unified_analyzer.py`, `analysis_tasks.py`).
- Duplicate service logic (both agents add a `fetchGames` variant).
- Produce merge conflicts in long-lived files.

This workflow prevents that.

---

## Isolation Principles

### 1. One agent owns one layer at a time

```
Agent A: backend service layer (analysis)
Agent B: frontend data layer (React Query hooks + api.ts additions)
Agent C: frontend UI layer (components + pages)
```

Agents A and B can work in parallel only if Agent B's `api.ts` additions are new endpoints (no edits to existing functions). Agents B and C can work in parallel as long as the component interface is agreed in advance.

### 2. Shared files are locked per agent

These files are high-conflict — only one agent touches them at a time:

| File | Lock reason |
|------|-------------|
| `backend/app/tasks/analysis_tasks.py` | All async tasks converge here |
| `backend/app/app.main.py` | Router registration |
| `frontend/src/lib/api.ts` | All API client functions |
| `frontend/src/types/index.ts` | Shared TypeScript types |
| `frontend/src/pages/_app.tsx` | Global providers |
| `backend/alembic/versions/` | Migration files are ordered and fragile |

### 3. Agree on interfaces before parallel work

Before splitting work between agents:

```markdown
Interface contract for feature X:

Backend will expose:
  POST /api/v1/users/{id}/patterns/analyze → { task_id: string }
  GET  /api/v1/users/{id}/patterns         → PatternResult[]

Frontend will consume:
  api.patternApi.triggerAnalysis(userId: string): { taskId: string }
  api.patternApi.getPatterns(userId: string): PatternResult[]

TypeScript type:
  interface PatternResult {
    id: string
    category: string
    frequency: number
    recommendation: string
  }
```

Both agents commit to this contract. Neither changes the interface during implementation without coordinating.

---

## Branch Strategy for Parallel Work

```
staging
  ├── feat/backend-patterns          ← Agent A (backend service + route)
  ├── feat/frontend-patterns-api     ← Agent B (api.ts + hooks)
  └── feat/frontend-patterns-ui      ← Agent C (components + page)
```

Merge order:
1. `feat/backend-patterns` → staging (API endpoint available)
2. `feat/frontend-patterns-api` → staging (depends on backend contract)
3. `feat/frontend-patterns-ui` → staging (depends on hooks from step 2)

If steps 2 and 3 are independent (UI can mock the API), they can merge in any order.

---

## Context Isolation

Each agent session should receive:

```markdown
## Your Scope

You are working ONLY on: [specific files/layer]

Do not modify:
- [locked shared files]
- [other agent's scope]

Interface contract (read-only):
- [agreed API shape]
- [agreed TypeScript types]

Reference:
- Backend patterns: workflows/backend-workflow.md
- Frontend patterns: workflows/frontend-workflow.md
- Architecture rules: .cursor/rules/architecture.mdc
```

Giving each agent a clear scope guard prevents "while I was here" modifications to shared files.

---

## Conflict Resolution

When a merge conflict occurs:

1. **Identify who owns the conflict area** (which agent's scope is it?).
2. **The owning agent resolves** — the other agent's change was out of scope.
3. **If both agents have a legitimate claim**, escalate to the human.
4. **Never auto-resolve** a conflict in a migration file, `api.ts`, or `_app.tsx` — always human-reviewed.

---

## Communication Protocol

Agents communicate state through:

1. **Branch names** — `feat/<layer>-<topic>` makes scope visible.
2. **PR descriptions** — document the interface contract and dependencies.
3. **Commit messages** — `feat(api): add patternApi.triggerAnalysis()` makes the change searchable.
4. **This document** — update the interface contracts section when new features are planned.

---

## Agentic Engineering Task Prompt Template

When assigning a task to a new agent session:

```markdown
## Task: [Feature Name] — [Layer]

You are implementing the [backend service / frontend hook / UI component] for [feature].

**Scope:** Only touch files in [directory list].
**Do not modify:** [locked files list].
**Interface contract:** [agreed API shape and types].

**Workflow to follow:** workflows/[backend|frontend]-workflow.md
**Architecture rules:** .cursor/rules/architecture.mdc

Before starting:
1. Read AGENTS.md.
2. Read the workflow document above.
3. Run the grep suite from skills/grep-loop-review.md (quick check) on the current codebase to understand the existing surface.
4. Confirm the interface contract matches what you'll implement.
5. Implement the minimal working version.
6. Run type-check and architecture grep before creating the PR.
```
