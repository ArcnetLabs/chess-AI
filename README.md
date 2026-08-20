# ChessRun

An AI chess coach. ChessRun connects to a user's Chess.com account, fetches and analyzes their recent games with Stockfish in the background, detects recurring weaknesses, builds a playing profile, and coaches the user through a conversational interface.

## 🎯 Product Definition

ChessRun is not a chess analytics dashboard. The coaching conversation is the product. Game analysis exists to improve coaching quality, and the playing profile provides coaching context. Users interact with personalized coaching conversations generated from game analysis, not reports or analytics pages.

The core product loop: Onboarding → Coaching Conversation → Game Analysis → Playing Profile → Personalized Coaching → back to conversation.

## 👥 Target Audience

- Casual to intermediate Chess.com players who want to improve their skills
- Coaches who want to provide feedback faster
- Competitive hobbyists tracking performance trends

## 🚀 Core Features

- **Chess.com Integration**: Username linking + game archive fetch via API (with ETag/Last-Modified caching)
- **Game Analysis**: PGN parsing and engine evaluation (Stockfish 16) in background Celery jobs
- **Pattern Detection**: Phase weaknesses, opening weaknesses, and blunder clusters with severity scoring
- **Playing Profile**: Append-only profile snapshots built from analyzed games (requires ≥10 games)
- **AI Coach Chat**: Conversational coaching grounded in profile, patterns, and semantic memory; LLM fallback chain (Ollama → OpenRouter → OpenAI) with prompt-based citations
- **Semantic Memory**: pgvector embeddings of detected patterns, retrieved to ground coach answers
- **Retention**: Weekly summary/digest emails (stub delivery) and in-app notification feed

## 🛠 Tech Stack

### Backend
- **Framework**: Python FastAPI
- **Chess Engine**: Stockfish 16 + python-chess (centralized engine pool)
- **Database**: PostgreSQL (Supabase, pgvector) + Redis (caching, job status, chat sessions, queues)
- **Workers**: Celery for background analysis, pattern detection, and scheduled jobs
- **LLM**: Ollama → OpenRouter → OpenAI fallback chain via a single `AIClient`

### Frontend
- **Framework**: Next.js 14 (Pages Router) with TypeScript
- **Styling**: Tailwind CSS
- **State/Data**: React Query, Zustand, axios (single API boundary)
- **Auth**: Supabase passwordless (magic link)

### Infrastructure
- **Containerization**: Docker & Docker Compose
- **Hosting**: Frontend on Netlify, backend + Celery on Render
- **Background Jobs**: Celery with Redis broker

## 📁 Project Structure

```
chess-AI/
├── backend/                 # Python FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes (thin HTTP shell)
│   │   ├── core/           # Config, database, logging
│   │   ├── middleware/     # JWT auth, ownership checks
│   │   ├── models/         # SQLAlchemy models
│   │   ├── services/       # Business logic (analysis, patterns, coaching, chat, games…)
│   │   └── tasks/          # Celery background tasks
│   ├── alembic/            # Schema migrations
│   ├── tests/              # Backend tests (pytest)
│   ├── scripts/            # Manual smoke/diagnostic scripts
│   └── requirements.txt
├── frontend/               # Next.js frontend
│   └── src/
│       ├── components/     # React components (coach workspace)
│       ├── pages/          # Next.js pages (auth, coach)
│       ├── hooks/          # React Query hooks
│       ├── services/       # API service wrappers
│       ├── store/          # Zustand chat store
│       ├── lib/            # API client, supabase clients, auth helpers
│       └── types/          # TypeScript types
├── docs/                   # Canonical documentation (see docs/README.md)
├── reference/              # Library reference material for agents
├── skills/                 # Agent workflow guides
├── workflows/              # Engineering workflow docs
├── scripts/                # Review-loop enforcement scripts
└── docker-compose.yml      # Local dev stack (postgres, redis, backend, frontend, celery)

## 🏗 Development Status

Shipped to production (`main`) across three phases:

### Phase 1: Backend intelligence core — ✅ Complete
Pattern detection (phase weakness, opening weakness, blunder clusters), pattern persistence, profile builder, pattern-aware recommendation engine, Redis chat sessions, and coach context assembly.

### Phase 2: Retention & visualization — 🔄 Partially complete
Auto-analysis pipeline (post-fetch auto-queue, job status + SSE streaming), game detail API + coach handoff, scheduled sync, and weekly summary stub. UI units (game viewer, pattern pages) are deferred until the product calls for them.

### Phase 3: Advanced AI & training — ✅ Backend complete
pgvector semantic memory with embedding/retrieval pipeline, coach prompt v2 grounded in retrieved memories, 50-case grounding eval, training plan + drill generator + progress tracking, weekly digest, in-app notifications, and the LLM provider wiring (Ollama → OpenRouter → OpenAI).

### Current focus
The MVP is the conversational coach workspace. Frontend UI is aligned to the ChessRun coach UX; remaining work is Phase 2/3 UI (game viewer, pattern visualization, training UI) and live E2E validation. See [`docs/execution/feature-progress-tracker.md`](docs/execution/feature-progress-tracker.md) for the live roadmap.

**Future directions (not MVP):** YouTube lesson learning engine, training mode and drill lifecycle, standalone analytics dashboards, scheduled report exports, and expanded coaching features.

## 🚦 Getting Started

### Prerequisites
- **Docker & Docker Compose** (for containerized deployment)
- **Node.js 18+** (for local frontend development)
- **Python 3.11+** (for local backend development)
- **PostgreSQL** (Supabase or local instance)
- **Redis** (optional, for caching)

### Option 1: Docker (Production-like)
```bash
# Clone and navigate to project
git clone https://github.com/ArcnetLabs/chess-AI.git
cd chess-AI

# Start all services
docker-compose up --build

# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API docs: http://localhost:8000/docs
```

### Option 2: Local Development (Recommended)

#### Backend Setup
```powershell
# Navigate to backend
cd backend

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Copy environment file and configure
cp .env.example .env
# Edit .env with your Supabase credentials

# Run the backend server
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

**Backend will be available at:** `http://localhost:8000`  
**API Documentation:** `http://localhost:8000/docs`

#### Frontend Setup
```powershell
# Navigate to frontend (open new terminal)
cd frontend

# Install dependencies
npm install

# Copy environment file and configure
cp .env.local.example .env.local
# Edit .env.local: NEXT_PUBLIC_API_URL=http://localhost:8000

# Run the frontend server
npm run dev
```

**Frontend will be available at:** `http://localhost:3000`

### Environment Configuration

**Backend `.env` requires:**
- `SECRET_KEY` - Generate with: `python -c 'import secrets; print(secrets.token_urlsafe(32))'`
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_ANON_KEY` - Supabase anon key
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key
- `DATABASE_URL` - PostgreSQL connection string

See `backend/.env.example` for full configuration options.

## 🎨 Design Philosophy

- **Conversation First**: The coach chat is the primary workspace; everything else is secondary
- **Dark & Quiet**: Utility-first dark interface with an emerald accent for primary actions
- **Coach, Not Engine**: Insights read like a human coach's scouting report, not an engine dump

## 🔮 Future Features

- YouTube lesson learning engine (video → annotated PGN → interactive practice)
- Training mode and drill lifecycle UI
- Opening repertoire clustering (ECO → family → winrate)
- Opponent-strength normalization (performance by rating buckets)
- Tactical motif detection (forks, pins, back-rank weakness)
- Personalized study plans and progress tracking
- Social leaderboard / community comparisons
- Browser extension integration

The canonical product direction lives in [`docs/product/CHESSRUN_MVP_UX.md`](docs/product/CHESSRUN_MVP_UX.md); dashboard, report, and training-mode features are treated as future-facing unless confirmed there.

## 📄 License

MIT License - see LICENSE file for details
