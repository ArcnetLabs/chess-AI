# ChessIQ — System Audit (2026-05-26)

This directory contains a complete, evidence-based audit of the ChessIQ repository conducted before any further feature development. All documents in this folder are **read-only deliverables** — they describe the system's current state, divergences from the FRD, and the remediation plan.

**Audited by:** Principal-engineer audit pass (read-only mapping, no code changes).  
**Audit date:** 2026-05-26  
**Branch audited:** `staging` HEAD as of audit start.

---

## Why this audit exists

The repository is not greenfield. Multiple developers and AI-assisted workflows have modified the system over time, leaving:

- Partial implementations
- Duplicate services
- Abandoned scaffolding (notably Supabase Auth)
- Incorrect deployment configurations
- Architecture rule violations

Before adding any new feature, the team must have **complete system awareness** of what is built, what is broken, what is duplicated, and what is missing.

---

## Documents

### 1. [`system-state-audit.md`](./system-state-audit.md) — Start here
The master document. Subsystem-by-subsystem health table, top-5 critical issues, all 4 architecture diagrams (request flow, frontend flow, analysis pipeline, auth reality), Phase 1–6 summary, and pointers to the deeper docs below.

**Read this first.** Everything else is supporting detail.

### 2. [`backend-audit.md`](./backend-audit.md)
Deep dive into `backend/` — entry-point mismatches, route-by-route findings, service-layer fragmentation, database hygiene (SQLite fallback, auto-create), Celery state, chat subsystem issues, and a current-state backend dependency diagram.

### 3. [`frontend-audit.md`](./frontend-audit.md)
Deep dive into `frontend/` — the dual-auth problem in detail, the 971-line `dashboard.tsx`, the 425-line `index.tsx`, the orphaned chat components, the missing hooks layer, the conflicting HTTP clients, and a current-state frontend dependency diagram.

### 4. [`technical-debt-report.md`](./technical-debt-report.md)
**40 debt items** categorised by severity (P0 / P1 / P2 / P3), each with file:line evidence and a recommended action. Includes per-file size violations, architecture violations, and the expected output of the grep-loop review suite against today's `staging`.

### 5. [`architecture-divergence-report.md`](./architecture-divergence-report.md)
What the FRD describes vs what is built. Capability-by-capability table (5 built, 4 partial, 13 missing of 22), missing data model entities, missing workers, missing pages. Includes the **Path A / B / C decision matrix** for product leadership.

### 6. [`recommended-remediation-roadmap.md`](./recommended-remediation-roadmap.md)
The prioritised action plan. **42 actionable items** sequenced across 4 phases (P0 → P3) with effort estimates and acceptance criteria per phase. Includes a dependency decision tree for parallel execution.

---

## Top-Level Findings (Headline)

### 5 Critical Issues That Block Production
1. **All API endpoints are unauthenticated.** `get_current_user` is imported by zero route files.
2. **Deployment is broken.** `render.yaml` and `docker-compose.yml` reference non-existent modules.
3. **Stockfish architecture is fragmented.** 10 files instantiate the engine; the pool exists but is bypassed.
4. **Database silently falls back to SQLite** in production code paths — data-loss risk.
5. **Two parallel authentication systems coexist** with no integration; the recently-added Supabase scaffold likely breaks the working Chess.com login flow.

### Subsystem Health Score
- **Backend:** 3.9 / 10 — salvageable; requires P0 fixes
- **Frontend:** 3.1 / 10 — oversized pages, missing hooks layer, dual-auth conflict
- **FRD coverage:** ~36% — the differentiator (pattern recognition) is unimplemented

### Recommended Path Forward (Path C — Hybrid)
1. **3 weeks of P0 work** to make the system secure and deployable
2. **3 weeks of P1 work** to consolidate the architecture
3. **4 weeks of P2 work** to repair the frontend
4. **12+ weeks of P3 work** to build the FRD's signature features

---

## How to use this audit

### If you are a developer or AI agent picking up this repo
1. Read `system-state-audit.md` end-to-end.
2. Read whichever deep-dive matches your area of work (`backend-audit.md` or `frontend-audit.md`).
3. Before touching code, confirm the area you're working on has no open P0/P1 items in `technical-debt-report.md`.
4. If your work touches an FRD capability that's marked missing, check `architecture-divergence-report.md` first.

### If you are product / engineering leadership
1. Read `system-state-audit.md` Executive Summary.
2. Read `architecture-divergence-report.md` §8 — Decision Required (Path A/B/C).
3. Use `recommended-remediation-roadmap.md` to sequence sprints.

### If you are auditing future drift
1. Run `.\scripts\review-loops\full-review.ps1` against the latest `staging`.
2. Compare against the expected violations in `technical-debt-report.md` §12.
3. Net-new violations should be filed against the contributor; net-removed violations are progress.

---

## Audit Methodology

This audit used:

- **Direct source inspection** (Read tool) on 25+ critical files including all route files, key services, config, models, deployment YAMLs, and FRD documents
- **Glob enumeration** of the complete backend + frontend source trees
- **Targeted ripgrep searches** for:
  - Stockfish instantiation sites (10 found)
  - LLM call sites (clean — 1 canonical + 1 duplicate)
  - SessionLocal in routes (3 found)
  - `get_current_user` import sites (zero — confirmed the auth gap)
  - Service file duplication patterns
- **Cross-reference verification** of `render.yaml`, `docker-compose.yml`, `backend/app/__main__.py`, `__init__.py`, `core/database.py`, `core/config.py`
- **FRD-to-code mapping** comparing claims in `docs/requirements/FRD_TECHNICAL.md` against actual file locations

**No code was modified during this audit.** All findings include file paths and (where given) line numbers as evidence.

---

## Cross-References

This audit explicitly references:
- `docs/product/FRD_PRODUCT.md`
- `docs/requirements/FRD_TECHNICAL.md`
- `docs/architecture/AI_MODEL_STRATEGY.md`
- `docs/architecture/MEMORY_RETRIEVAL_CONTEXT_ARCHITECTURE.md`
- `docs/architecture/reference-context-system.md`
- `.cursor/rules/architecture.mdc`
- `.cursor/rules/backend.mdc`
- `.cursor/rules/frontend.mdc`
- `scripts/review-loops/*.ps1`
- `skills/grep-loop-review.md`
- `skills/architecture-review.md`
- `skills/refactor-loop.md`
- `skills/duplication-detection.md`
- `workflows/grep-review-process.md`

---

## Sign-off

This audit is the authoritative snapshot of system state as of 2026-05-26. Do not modify these documents. If the system changes substantially, run a **new audit** and store it as `docs/audit/<date>/` rather than editing this one — the historical record matters.

The next audit should be scheduled when:
- All P0 items are closed (validating the remediation worked), OR
- A major architectural decision is made (new auth system, new database, new framework), OR
- 90 days have passed (preventive freshness check)
