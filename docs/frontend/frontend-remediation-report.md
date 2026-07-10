# Frontend Architecture Remediation Report

**Date:** 2026-05-26  
**Scope:** ChessRun Pages Router frontend — dashboard decomposition, hooks layer, API consolidation, polling isolation, chat wiring
**Out of scope:** New product features, UI redesign, pattern-recognition dashboards

---

## Summary

The frontend was refactored from a monolithic ~970-line `dashboard.tsx` into a layered structure: thin pages, feature containers, reusable components, React Query hooks, and isolated polling services. Chat now routes through the shared axios client with authenticated user context. Type-check passes with zero errors.

---

## Target structure (achieved)

```
frontend/src/
├── components/
│   ├── dashboard/          # Reusable dashboard UI sections
│   └── chat/               # Global chatbot (wired via _app.tsx)
├── features/
│   ├── dashboard/          # DashboardView + game display utils
│   └── home/               # Placeholder for home redirect domain
├── hooks/                  # React Query + workflow hooks
├── services/               # Polling + chat session wrappers
├── lib/api.ts              # Canonical HTTP client (incl. chat)
├── pages/                  # Thin route shells only
└── store/                  # Zustand UI state (chat)
```

---

## Extracted components

| Component | Path | Responsibility |
|-----------|------|----------------|
| `PerformanceCard` | `components/dashboard/PerformanceCard.tsx` | Metric card with optional trend |
| `CoachingInsightCard` | `components/dashboard/CoachingInsightCard.tsx` | Single AI recommendation row |
| `MoveQualityChart` | `components/dashboard/MoveQualityChart.tsx` | Pie chart + shared `buildMoveQualityChartData` |
| `PhasePerformanceChart` | `components/dashboard/PhasePerformanceChart.tsx` | ACPL bar chart by game phase |
| `ChartEmptyState` | `components/dashboard/PhasePerformanceChart.tsx` | Shared empty chart placeholder |
| `DashboardHeader` | `components/dashboard/DashboardHeader.tsx` | Welcome + connection status |
| `GamesSummaryBar` | `components/dashboard/GamesSummaryBar.tsx` | Fetched vs analyzed counts |
| `DashboardActions` | `components/dashboard/DashboardActions.tsx` | Sync / analyze / re-analyze buttons |
| `PerformanceOverview` | `components/dashboard/PerformanceOverview.tsx` | Four summary metric cards |
| `GamesList` | `components/dashboard/GamesList.tsx` | Collapsible game list with per-game analyze |
| `CoachingInsightsSection` | `components/dashboard/CoachingInsightsSection.tsx` | Recommendations list or empty state |
| `EmptyAnalysisState` | `components/dashboard/EmptyAnalysisState.tsx` | Onboarding CTA when no analysis |
| `DashboardLoadingState` | `components/dashboard/DashboardStates.tsx` | Full-page loading spinner |
| `DashboardErrorState` | `components/dashboard/DashboardStates.tsx` | Missing user fallback |

**Feature container:** `features/dashboard/DashboardView.tsx` — composes hooks + components; owns modal wiring only.

**Page shell:** `pages/dashboard.tsx` — 5 lines; renders `<DashboardView />`.

---

## Hooks created

| Hook | Path | Responsibility |
|------|------|----------------|
| `useCurrentUser` | `hooks/useCurrentUser.ts` | `['me']` query, onboarding redirect, loading gate |
| `useDashboardQueries` | `hooks/useDashboardQueries.ts` | Analysis summary, recommendations, games (React Query) |
| `useFetchGames` | `hooks/useFetchGames.ts` | Sync recent games mutation + toasts |
| `useGameAnalysis` | `hooks/useGameAnalysis.ts` | Batch/single analyze orchestration + modal state |
| `useChatSession` | `hooks/useChatSession.ts` | Bind chat session to authenticated user id |

Barrel export: `hooks/index.ts`

---

## Services / polling isolation

| Module | Path | Responsibility |
|--------|------|----------------|
| `analysisPollingService` | `services/analysisPollingService.ts` | `startBatchAnalysisPolling`, `startSingleGameAnalysisPolling` — no React, pure interval logic with cleanup |
| `chatService` | `services/chatService.ts` | Session state wrapper; delegates HTTP to `lib/api.ts` |

**Removed from pages:** All `setInterval` / inline polling in `dashboard.tsx`. Polling intervals and max-poll limits live in one service file.

**Polling fix:** Batch completion now compares *newly analyzed* games against `games_queued` (baseline snapshot), fixing a pre-existing bug where total analyzed count could satisfy completion immediately.

---

## API client consolidation

| Change | Detail |
|--------|--------|
| Added `chatApi` | `lib/api.ts` — `createSession`, `sendMessage`, `getHistory`, `deleteSession`, `quickAnalysis` |
| Refactored `chatService` | Removed raw `fetch()`; uses `api.chat.*` with Supabase JWT via axios interceptor |
| Exported `api.chat` | Single entry point alongside `users`, `games`, `analysis`, `insights` |

---

## Chat wiring

| Before | After |
|--------|-------|
| Chat mounted in `_app.tsx` but session had no user id | `useChatSession(userId)` on dashboard initializes session with backend user id |
| `chatService` used standalone `fetch` (no auth header) | All chat calls go through authenticated axios client |
| `chatStore.sendMessage` omitted user id | Passes `userId` from store into `chatService.sendMessage` |

Global chatbot remains in `_app.tsx` (`<Chatbot />`); dashboard hook ensures session is provisioned when the user lands on the main app surface.

---

## Auth-flow consistency

| Route | Pattern |
|-------|---------|
| `/` (`index.tsx`) | SSR redirect via `getServerUser` → `/dashboard` or `/auth/login` (unchanged; already compliant) |
| `/dashboard` | Client `useCurrentUser` → redirect to `/onboarding/link-chesscom` if `chesscom_username` is null |
| API 401 | Axios interceptor → `/auth/login?next=...` (unchanged) |

No legacy `?username=` query param usage remains on the dashboard.

---

## Page weight (before → after)

| File | Before | After |
|------|--------|-------|
| `pages/dashboard.tsx` | ~970 lines | 5 lines |
| `pages/index.tsx` | ~33 lines | ~33 lines (already thin SSR redirect) |

---

## Architectural improvements

1. **Separation of concerns** — Pages route; features compose; components render; hooks fetch; services poll.
2. **DRY charts** — Duplicate inline pie chart data (defined twice in old dashboard) replaced by `MoveQualityChart` + `buildMoveQualityChartData`.
3. **Game display utils** — Opponent/result formatting extracted to `features/dashboard/utils/gameDisplay.ts`.
4. **React Query ownership** — Server state queries moved out of page into `useDashboardQueries` / `useCurrentUser`.
5. **Debug noise removed** — `console.log` polling traces removed from dashboard surface.
6. **Repository invariants** — No direct `axios` or `fetch` in `pages/` or new `components/`; chat auth aligned with backend JWT flow.

---

## Remaining frontend debt

| Item | Priority | Notes |
|------|----------|-------|
| `AnalysisProgressModal` auto-complete timer | Medium | Still uses estimated time heuristic instead of polling state; should consume `useGameAnalysis` progress directly |
| Stronger analysis summary types | Low | `api.analysis.getSummary` returns `any`; add `AnalysisSummary` interface in `types/` |
| `useGameAnalysis` + React Query mutations | Low | Analyze/fetch could use `useMutation` for consistent pending/error state |
| Chat on non-dashboard routes | Low | `useChatSession` only runs on dashboard; auth pages won't pre-warm chat (acceptable for now) |
| Automated frontend tests | Medium | No Jest/Playwright suite yet; type-check is the only gate |
| `features/home` placeholder | Low | Home redirect logic stays in `pages/index.tsx` (SSR requirement); feature folder reserved for future marketing shell |
| Orphan audit | Low | `LineChart` import was dead code in old dashboard; removed. Full component usage audit not yet scripted |
| Analysis cancel endpoint | Low | `handleStopAnalysis` stops polling client-side; backend cancel API still commented out |

---

## Verification

```bash
cd frontend && npm run type-check   # passes (2026-05-26)
```

Architecture grep (manual):

```bash
rg "axios\.(get|post|put|delete)" frontend/src/components/ frontend/src/pages/
rg "fetch\(" frontend/src/components/ frontend/src/pages/
rg "supabase\.auth\." frontend/src/pages/
```

Expected: zero violations in pages/components for raw HTTP and auth bypass.

---

## Files touched (high level)

- **Added:** `hooks/*`, `components/dashboard/*`, `features/dashboard/*`, `services/analysisPollingService.ts`, `docs/frontend/frontend-remediation-report.md`
- **Refactored:** `pages/dashboard.tsx`, `lib/api.ts`, `services/chatService.ts`, `store/chatStore.ts`
- **Unchanged behavior:** Dashboard UX, auth redirects, global chatbot placement
