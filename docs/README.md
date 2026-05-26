# ChessIQ — Documentation Index

This directory is the canonical source of truth for ChessIQ (Chess Insight AI) documentation. It is organized by document _type_ so that both humans and AI agents can quickly locate the document they need.

> For the project overview, tech stack, and local development setup, see the root [`../README.md`](../README.md).

---

## Directory layout

```
docs/
├── README.md                       # This index
├── architecture/                   # System architecture & technical design
│   ├── AI_MODEL_STRATEGY.md
│   ├── MEMORY_RETRIEVAL_CONTEXT_ARCHITECTURE.md
│   ├── reference-context-system.md
│   ├── repository-invariants.md        # Authoritative architectural rules (paired with scripts/review-loops/)
│   └── stockfish-architecture.md       # Canonical Stockfish pool access (2026-05-26)
├── product/                        # Product requirements
│   └── FRD_PRODUCT.md
├── requirements/                   # Technical requirements
│   └── FRD_TECHNICAL.md
├── strategy/                       # Business / product strategy
│   ├── FUTURE_SERVICES_EXPANSION_STRATEGY.md
│   └── PRICING_MONETIZATION_STRATEGY.md
├── deployment/                     # Deployment & operations
│   ├── DEPLOYMENT_GUIDE.md
│   ├── DOCKER_GUIDE.md
│   ├── NETLIFY_DEPLOYMENT.md
│   └── infrastructure-stabilization-report.md   # P0 infra sign-off (2026-05-26)
├── html/                           # Rendered HTML version of the doc suite
│   ├── index.html
│   ├── frd_product.html
│   ├── frd_technical.html
│   ├── ai_model_strategy.html
│   ├── memory_retrieval_context_architecture.html
│   ├── pricing_monetization_strategy.html
│   ├── shared.css
│   └── shared.js
├── audit/                          # System state audit (2026-05-26)
│   ├── README.md                       # Audit index — START HERE
│   ├── system-state-audit.md           # Master findings doc
│   ├── backend-audit.md
│   ├── frontend-audit.md
│   ├── technical-debt-report.md
│   ├── architecture-divergence-report.md
│   └── recommended-remediation-roadmap.md
├── review-reports/                 # Generated grep-loop review reports (per-run telemetry)
│   └── README.md                       # How reports are produced and rotated
└── archive/                        # Historical implementation notes & reference guides
    └── legacy-docs/                # Generated reports, phase notes, one-off fix summaries
```

---

## Where to start

| If you are… | Read |
| --- | --- |
| New to the project | [`../README.md`](../README.md) → [`product/FRD_PRODUCT.md`](./product/FRD_PRODUCT.md) → [`audit/README.md`](./audit/README.md) |
| **Picking up the codebase after recent changes** | [`audit/system-state-audit.md`](./audit/system-state-audit.md) — current health, broken systems, remediation plan |
| Building a feature | [`audit/recommended-remediation-roadmap.md`](./audit/recommended-remediation-roadmap.md) (check P0 status first) → [`requirements/FRD_TECHNICAL.md`](./requirements/FRD_TECHNICAL.md) → relevant doc in [`architecture/`](./architecture/) |
| Deploying or running ops | [`deployment/infrastructure-stabilization-report.md`](./deployment/infrastructure-stabilization-report.md) → [`deployment/DEPLOYMENT_GUIDE.md`](./deployment/DEPLOYMENT_GUIDE.md) → [`deployment/DOCKER_GUIDE.md`](./deployment/DOCKER_GUIDE.md) |
| Working on AI / RAG / memory | [`architecture/AI_MODEL_STRATEGY.md`](./architecture/AI_MODEL_STRATEGY.md) + [`architecture/MEMORY_RETRIEVAL_CONTEXT_ARCHITECTURE.md`](./architecture/MEMORY_RETRIEVAL_CONTEXT_ARCHITECTURE.md) |
| Working on pricing / packaging | [`strategy/PRICING_MONETIZATION_STRATEGY.md`](./strategy/PRICING_MONETIZATION_STRATEGY.md) |
| Planning expansion | [`strategy/FUTURE_SERVICES_EXPANSION_STRATEGY.md`](./strategy/FUTURE_SERVICES_EXPANSION_STRATEGY.md) |

---

## Document categories

### Architecture (`architecture/`)
Authoritative technical design documents that describe how subsystems work.
- **`AI_MODEL_STRATEGY.md`** — Model selection, prompting, evaluation, and inference strategy for the AI subsystem.
- **`MEMORY_RETRIEVAL_CONTEXT_ARCHITECTURE.md`** — Long-term memory, retrieval, and context assembly architecture for the chatbot/coach.
- **`reference-context-system.md`** — Why reference-driven development matters, how the `reference/` + `prompts/` system reduces agent hallucination, and how to maintain it.
- **`repository-invariants.md`** — The authoritative list of architectural rules ChessIQ enforces. Paired with `scripts/review-loops/`, `.cursor/rules/`, and the review workflows. Changing a rule changes this document first.
- **`stockfish-architecture.md`** — Single canonical path for Stockfish via `engine_pool.py`; thread/queue safety and consumer map.

### Review reports (`review-reports/`)
Generated, rotating telemetry from `scripts/review-loops/full-review.ps1 -Report`. See [`review-reports/README.md`](./review-reports/README.md) for filename patterns, retention policy, and how they feed back into the implementation / architecture / refactor review loops.

### Product (`product/`)
- **`FRD_PRODUCT.md`** — Product functional requirements (features, user flows, target audience, success criteria).

### Requirements (`requirements/`)
- **`FRD_TECHNICAL.md`** — Technical functional requirements (APIs, data models, integrations, non-functional requirements).

### Strategy (`strategy/`)
- **`PRICING_MONETIZATION_STRATEGY.md`** — Pricing tiers, monetization model, packaging.
- **`FUTURE_SERVICES_EXPANSION_STRATEGY.md`** — Roadmap for service expansion beyond the core product.

### Deployment (`deployment/`)
- **`DEPLOYMENT_GUIDE.md`** — General deployment guide across environments.
- **`DOCKER_GUIDE.md`** — Docker / Docker Compose specific deployment instructions. See also root `docker-compose.yml`, `docker-compose.production.yml`, and `Dockerfile.*` files.
- **`NETLIFY_DEPLOYMENT.md`** — Frontend (Next.js) deployment via Netlify. See also root `netlify.toml`.

For the Render.com configuration, see the root `render.yaml`.

### HTML build (`html/`)
A self-contained, statically-rendered HTML version of the document suite (product, technical, AI model, memory architecture, pricing). Open `html/index.html` in a browser to navigate.

### Archive (`archive/`)
Historical documents that have been superseded by the active docs above but retain reference value — Stockfish guides, Celery manuals, setup walkthroughs, user flow maps, and chatbot design docs. **Do not treat archive contents as current truth.** Files are prefixed with their original location when moved from `backend/`, `frontend/`, or the repo root.

Also contains archived Python scripts and SQL utilities (prefixed `backend_`) that were used for manual diagnostics during early development.

#### `archive/legacy-docs/`
Pure noise: generated phase-completion reports, status snapshots, one-off bugfix notes, and design tool artifacts. Retained only as an audit trail. Never reference these in active development.

---

## Conventions

- **Filenames:** `SCREAMING_SNAKE_CASE.md` for top-level documents inside each category folder.
- **Source of truth:** Markdown files in this directory are the source of truth. The `html/` build is generated from them and is for browsing/sharing.
- **New documents:** Place under the category folder that best matches the document type. If no category fits, propose a new folder rather than dropping files at the `docs/` root.
- **Archiving:** When a document is superseded, move it into `archive/` rather than deleting it.

---

**Maintained by:** ChessIQ team
