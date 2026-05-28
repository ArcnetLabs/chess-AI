# ChessIQ Feature Execution

**Status:** Active — post-remediation controlled feature development  
**Start here after remediation:** [`feature-priority-map.md`](./feature-priority-map.md)

---

## Documents

| Document | Purpose |
|----------|---------|
| [`feature-progress-tracker.md`](./feature-progress-tracker.md) | **Live progress** — done / staging / deferred / not started by unit ID |
| [`implementation-state-and-governance-2026-05-26.md`](./implementation-state-and-governance-2026-05-26.md) | Audit snapshot, task matrix, merge governance |
| [`feature-priority-map.md`](./feature-priority-map.md) | Moat systems, dependencies, cross-cutting implications, priority scores |
| [`feature-execution-roadmap.md`](./feature-execution-roadmap.md) | Phase 1–3 features, sequencing, exit checklists, branch strategy |
| [`multi-agent-development-strategy.md`](./multi-agent-development-strategy.md) | Four agent roles, allowed/forbidden paths, review duties |
| [`parallel-development-workflows.md`](./parallel-development-workflows.md) | Isolation, branches, PR flow, merge order, checkpoints |
| [`review-loop-enforcement.md`](./review-loop-enforcement.md) | Grep gates, architecture validation, duplication, performance |

---

## Recommended reading order

1. **feature-progress-tracker.md** — what's done, in flight, and deferred *(start here for status)*  
2. **feature-priority-map.md** — understand what to build and why  
3. **feature-execution-roadmap.md** — pick the current phase unit (e.g. P2-AA-03)  
3. **multi-agent-development-strategy.md** — assign agent role for the unit  
4. **parallel-development-workflows.md** — check if work can run in parallel  
5. **review-loop-enforcement.md** — run gates before opening the PR  

---

## Phase summary

| Phase | Focus | First units |
|-------|-------|-------------|
| **1** | Backend intelligence | Pattern schema, pattern engine MVP, profile builder, recommendation v2 |
| **2** | Retention & visualization | SSE analysis status, game viewer, pattern dashboard |
| **3** | Advanced AI & training | pgvector RAG, adaptive drills, proactive coaching |

---

## Related

- Remediation complete: [`../frontend/frontend-remediation-report.md`](../frontend/frontend-remediation-report.md), [`../review-reports/backend-consolidation-report.md`](../review-reports/backend-consolidation-report.md)
- Product vision: [`../product/FRD_PRODUCT.md`](../product/FRD_PRODUCT.md)
- Memory architecture: [`../architecture/MEMORY_RETRIEVAL_CONTEXT_ARCHITECTURE.md`](../architecture/MEMORY_RETRIEVAL_CONTEXT_ARCHITECTURE.md)
- Agent conventions: [`../../AGENTS.md`](../../AGENTS.md)
