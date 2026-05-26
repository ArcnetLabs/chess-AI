# Authentication System

**Status:** canonical · **Owner:** platform · **Last updated:** 2026-05-26

ChessIQ's authentication architecture is built around a single principle:

> **Supabase Auth is the canonical identity layer.**
> Chess.com usernames are linked profile data, not identity.

This document describes the end-to-end flow, the boundaries between the
frontend, backend, and Supabase, and the rules that future changes must
preserve.

---

## 1. Why Supabase

The pre-2026-05 system identified users by Chess.com username — a string
the user typed into a form, with no proof of ownership and no shared
identity across devices. That made it impossible to:

- enforce ownership on the API (any client could hit `/users/3/...`),
- persist session state across browsers,
- attach billing, subscriptions, or future social features to a user,
- recover access after a username change on Chess.com.

Supabase Auth gives us:

- email/password sign-up with confirmation (and OAuth providers when we
  enable them),
- cookie-based sessions with silent refresh in middleware,
- a stable user UUID (`auth.users.id`) we can use as a foreign key,
- a JWT we can verify locally on the backend with PyJWT — no per-request
  round-trip to Supabase.

Everything else — Chess.com username, ratings, games, analyses,
insights, AI coaching, future subscriptions — hangs off the local
`users` row that is keyed by `supabase_user_id`.

---

## 2. Data model

```text
                    Supabase Auth (managed)
                    ┌──────────────────────┐
                    │ auth.users           │
                    │   id (UUID)          │
                    │   email              │
                    │   ...                │
                    └──────────┬───────────┘
                               │  sub  (JWT claim)
                               ▼
                    Local Postgres
                    ┌──────────────────────────────────────┐
                    │ public.users                         │
                    │   id (int PK)                        │
                    │   supabase_user_id (UUID, UNIQUE)    │  ← canonical
                    │   chesscom_username (UNIQUE, NULLABLE)│  ← linked
                    │   email (UNIQUE, NULLABLE)           │
                    │   tier, ratings, etc.                │
                    └──────────┬───────────────────────────┘
                               │
                               ▼
                    public.games, public.analyses, public.user_insights …
                    (all carry user_id FK → public.users.id)
```

`supabase_user_id` is a `VARCHAR(36)` (UUIDv4 string) to keep the
column portable between Postgres (canonical) and the SQLite dev
fallback. The value is always the `sub` claim from the Supabase JWT.

The migration adding the column is
[`backend/alembic/versions/0005_add_supabase_user_id.py`](../../backend/alembic/versions/0005_add_supabase_user_id.py).

---

## 3. End-to-end flow

### 3.1 Sign-up & first contact

```
Browser                                       Backend
───────                                       ───────
 1. User lands on /auth/signup
 2. signUp(email, password)  ──────────►  Supabase
                                          (sends confirmation email)
 3. User clicks email link
 4. /auth/callback exchanges PKCE code
    for a session cookie via Supabase
 5. Redirect to /dashboard
 6. dashboard.tsx renders
    └─ GET /users/me with Authorization: Bearer <JWT>
                                  ───────►   verify_jwt(token)
                                             └─ local HS256 decode
                                                using SUPABASE_JWT_SECRET
                                             └─ extract sub, email
                                             └─ look up users by
                                                supabase_user_id
                                             └─ AUTO-PROVISION row
                                                if first contact
                                  ◄───────   return User { chesscom_username: null }
 7. chesscom_username is null
    redirect → /onboarding/link-chesscom
 8. POST /users/me/link-chesscom { chesscom_username }
                                  ───────►   validate against Chess.com API
                                             persist on current_user row
                                             queue background games fetch
                                  ◄───────   return User { chesscom_username: "…" }
 9. redirect → /dashboard (data loads)
```

### 3.2 Returning user

```
1. Browser cookie carries Supabase refresh token.
2. middleware.ts calls supabase.auth.getUser() on every request:
     - validates JWT signature & expiry
     - silently refreshes the access token if needed
     - sets the refreshed cookie on both request and response
3. Pages render, axios attaches the access token, backend verifies.
```

### 3.3 Sign-out

Frontend calls `supabase.auth.signOut()` which clears the cookie.
The backend is stateless — no logout endpoint to call.

---

## 4. Backend boundaries

### 4.1 JWT verification

Implemented in
[`backend/app/services/auth/auth_service.py`](../../backend/app/services/auth/auth_service.py)
as `AuthService.verify_jwt(token)`.

- **Production path:** local `pyjwt.decode()` against
  `settings.SUPABASE_JWT_SECRET` with audience `authenticated`. Hot-path
  safe — no I/O.
- **Dev fallback:** if `SUPABASE_JWT_SECRET` is unset, fall back to
  `supabase.auth.get_user(token)` which performs an HTTP call to
  Supabase. A warning is logged. Production deployments **must** set
  the secret.

The secret lives in env (`SUPABASE_JWT_SECRET`) and is documented in
`backend/.env.example`. It is the **JWT Secret** field from the
Supabase dashboard under *Settings → API → JWT Settings*, not the
service-role key.

### 4.2 Dependency: `get_current_user`

Implemented in
[`backend/app/middleware/auth_middleware.py`](../../backend/app/middleware/auth_middleware.py).

- Extracts `Bearer <jwt>` from the `Authorization` header.
- Calls `AuthService.verify_jwt(token)`.
- Looks up the local `users` row by `supabase_user_id`.
- **Auto-provisions** the row on first contact so the Supabase sign-up
  flow doesn't need a separate "register on the backend" step.
- Returns the local `User` (NOT a dict — every route gets a real
  ORM instance and can read `.id`, `.tier`, `.chesscom_username`, etc).

A sibling `get_current_user_optional` returns `None` instead of raising
401 — used only for endpoints that work for both anonymous and signed-in
users.

### 4.3 Ownership: `require_ownership`

Every route whose path includes `{user_id}` must call
`require_ownership(current_user, user_id)` immediately after resolving
the auth dependency. Routes that operate on user-owned resources
(`/games/game/{game_id}`, `/insights/insight/{insight_id}`, etc.) load
the resource first then call `require_ownership(current_user, resource.user_id)`.

The helper raises a 403 if the IDs differ. It does not leak whether the
target resource exists — same response for "no such resource" and "not
yours" — which prevents enumeration attacks.

### 4.4 Route protection coverage

| Router                  | Protected? | Notes                                                                                          |
| ----------------------- | ---------- | ---------------------------------------------------------------------------------------------- |
| `/users/me*`            | Yes        | New canonical endpoints                                                                        |
| `/users/{user_id}/*`    | Yes        | Ownership-checked                                                                              |
| `/users/` (POST)        | Yes        | Back-compat shim — auth-required, links username to current user                               |
| `/users/` (GET list)    | Yes        | Restricted to own row until an admin role exists                                               |
| `/games/{user_id}/*`    | Yes        | Ownership-checked                                                                              |
| `/games/game/{game_id}` | Yes        | Game-ownership checked                                                                         |
| `/analysis/*`           | Yes        | Ownership-checked (user_id and/or game_id)                                                     |
| `/insights/*`           | Yes        | Ownership-checked (user_id and/or insight_id)                                                  |
| `/chat/*` (except `/chat/health`) | Yes (auth-only) | Session-level ownership deferred — sessions are in-memory and identified by UUID    |
| `/moves/*` (except `/moves/health`) | Yes (auth-only) | Stateless position analysis. Auth prevents anonymous Stockfish abuse           |
| `/health`, `/`          | No         | Public                                                                                         |

The single source of truth for these rules is enforced automatically by
[`scripts/review-loops/check-auth-guards.ps1`](../../scripts/review-loops/check-auth-guards.ps1).
See also [`docs/architecture/repository-invariants.md`](repository-invariants.md).

---

## 5. Frontend boundaries

### 5.1 Supabase client surface

| File                                   | Use case                                                       |
| -------------------------------------- | -------------------------------------------------------------- |
| `lib/supabase/client.ts`               | Browser-side singleton (React components, hooks, realtime)     |
| `lib/supabase/server.ts`               | Server-side per-request (getServerSideProps, API routes)       |
| `lib/auth/session.ts` (`getServerUser`)| Validate JWT server-side (never `getSession()` for authZ)      |
| `lib/auth/withAuth.ts`                 | HOC to gate pages behind a valid session                       |
| `middleware.ts`                        | Token refresh + protect `/dashboard`, redirect away from auth pages |

The same env vars (`NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`) flow through every layer.

### 5.2 JWT injection into API calls

`lib/api.ts` carries a single axios instance with a request interceptor
that reads the Supabase session and attaches the access token as a
`Bearer` header. The interceptor uses `supabase.auth.getSession()`
intentionally — we're forwarding the token, not authorizing locally; the
backend's PyJWT validation is the source of truth.

A response interceptor on 401 redirects the browser to
`/auth/login?next=<current path>` so expired tokens never strand the
user on a broken page.

### 5.3 Page surfaces

| Page                                    | Purpose                                                                                         |
| --------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `pages/index.tsx`                       | Server-side redirect: authed → `/dashboard`, unauthed → `/auth/login`                            |
| `pages/auth/login.tsx`                  | Email/password sign-in via Supabase                                                              |
| `pages/auth/signup.tsx`                 | Email/password sign-up via Supabase                                                              |
| `pages/auth/callback.tsx`               | PKCE / email-confirmation handler                                                                |
| `pages/onboarding/link-chesscom.tsx`    | Link a Chess.com username to the authenticated user                                              |
| `pages/dashboard.tsx`                   | Loads `/users/me`, redirects to onboarding if `chesscom_username` is null                        |

The legacy Chess.com-username pseudo-login at `/` is gone. The new
landing page is the SSR redirect.

---

## 6. Session lifecycle

| Event                          | Where                              | What happens                                                                                                            |
| ------------------------------ | ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Sign-up                        | `/auth/signup`                     | Supabase creates auth.users row; confirmation email sent                                                                |
| Email confirmation             | `/auth/callback`                   | `exchangeCodeForSession` writes the session cookie                                                                       |
| First authenticated API call   | Any backend route                  | Backend auto-provisions `public.users` row with `supabase_user_id`                                                       |
| Token approaching expiry       | `middleware.ts`                    | `supabase.auth.getUser()` triggers a silent refresh; new cookies written to response                                     |
| Frontend uses session          | Any page / `lib/api.ts`            | Cookie is the storage; `createBrowserClient` & `createServerClient` read it without exposing tokens to `localStorage`     |
| Sign-out                       | Anywhere on frontend               | `supabase.auth.signOut()` clears the cookie; subsequent requests miss the JWT and bounce to `/auth/login`                |

The backend keeps no session state. Each request carries its own JWT and
is verified independently.

---

## 7. Failure modes & responses

| Condition                                          | HTTP status | Detail                                                                              |
| -------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------- |
| Missing `Authorization` header                     | 401         | `Not authenticated` (FastAPI default for HTTPBearer)                                |
| Bearer header present but JWT invalid              | 401         | `Invalid access token: …`                                                           |
| JWT signature mismatch                             | 401         | `Invalid access token: Signature verification failed`                               |
| JWT expired                                        | 401         | `Access token expired`                                                              |
| JWT audience wrong                                 | 401         | `Access token has wrong audience`                                                   |
| Resolved user, accessing another user's resource   | 403         | `You can only access your own resources`                                            |
| Local user can't be auto-provisioned (DB error)    | 500         | `Failed to provision local user`                                                    |
| Linking a Chess.com username taken by someone else | 409         | `Chess.com username '…' is already linked to another account`                       |

Every 401 sets `WWW-Authenticate: Bearer` so clients (and the frontend's
axios interceptor) know to re-authenticate.

---

## 8. Invariants enforced by review tooling

The following invariants live in
[`docs/architecture/repository-invariants.md`](repository-invariants.md)
and are checked automatically by `scripts/review-loops/check-auth-guards.ps1`:

1. Every mutating route on `/users`, `/games`, `/analysis`, `/insights`,
   `/moves`, `/chat` declares `Depends(get_current_user)`.
2. No route in `backend/app/api` calls `supabase.auth.get_user()`
   directly — it goes through `AuthService.verify_jwt`.
3. Frontend `lib/` and `pages/` code never reads `getSession()` for
   authorization decisions; only `getServerUser()` is used.
4. The frontend axios client attaches `Authorization: Bearer` for every
   request to `/api/v1/*`.
5. Every `{user_id}` route calls `require_ownership(current_user, user_id)`.

---

## 9. Future work (explicitly out of scope for this remediation)

- Persist chat sessions per `current_user.id` so session-level ownership
  can be enforced (tracked under the analysis-pipeline remediation).
- Introduce an admin role and re-open `GET /users/` for admin clients.
- Move tier upgrades from the manual `/users/{user_id}/upgrade-to-pro`
  endpoint to a Stripe webhook-driven flow.
- Add OAuth providers (Google, GitHub) once the subscription / billing
  flow lands.
- Server-side enforcement that `supabase_user_id` matches the local
  `id` when issuing Supabase realtime channels.

Each of these has a dedicated entry on
[`docs/audit/recommended-remediation-roadmap.md`](../audit/recommended-remediation-roadmap.md).
