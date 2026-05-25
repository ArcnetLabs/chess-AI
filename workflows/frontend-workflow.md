# Frontend Engineering Workflow

How to implement frontend features in ChessIQ — Next.js Pages Router, React Query, and Supabase auth.

---

## Guiding Principles

1. **Data flow is unidirectional.** Browser → `api.ts` → FastAPI → data. Never bypass `api.ts` with raw axios in components.
2. **Pages are thin.** A page file's job is layout and routing. Data fetching belongs in hooks; display belongs in components.
3. **Auth is handled at two levels.** Middleware handles route protection at the edge (before the page loads). `withAuth` handles it at the `getServerSideProps` level for guaranteed server-side validation.
4. **Supabase is auth-only (current stage).** Application data comes from FastAPI. Do not query Supabase tables directly from the frontend until that architecture decision is explicitly made.

---

## Workflow Steps

### 1. Define the data contract

Before touching React, define:
- What API endpoint will this call? Does it exist in `api.ts`? If not, add it.
- What TypeScript types are needed? Add to `src/types/index.ts` or a new type file.

### 2. Add the API client function

Location: `frontend/src/lib/api.ts`

```typescript
// Group by resource — follow the existing pattern
export const insightApi = {
  getForUser: async (userId: string): Promise<UserInsight[]> => {
    const response = await apiClient.get<UserInsight[]>(`/users/${userId}/insights`)
    return response.data
  },
}
```

### 3. Create the React Query hook

Location: `frontend/src/hooks/use<Feature>.ts`

```typescript
export function useUserInsights(userId: string) {
  return useQuery({
    queryKey: ['insights', userId],
    queryFn: () => insightApi.getForUser(userId),
    enabled: !!userId,
    staleTime: 1000 * 60 * 5,
  })
}
```

### 4. Build the component (display only)

Location: `frontend/src/components/<Feature>/<ComponentName>.tsx`

- Component receives data as props — it does not fetch data.
- Loading and error states handled by the parent page, not inside the component.
- No `useEffect` for data fetching — use React Query.

### 5. Build the page

Location: `frontend/src/pages/<route>.tsx`

```typescript
// Protected page pattern
export default function InsightsPage({ userId }: { userId: string }) {
  const { data, isLoading, error } = useUserInsights(userId)
  if (isLoading) return <LoadingSpinner />
  if (error) return <ErrorMessage error={error} />
  return <InsightsList insights={data ?? []} />
}

export const getServerSideProps = withAuth(async (context, user) => {
  return { props: { userId: user.id } }
})
```

### 6. Run the checks

```bash
cd frontend
npm run type-check
npm run lint
```

---

## Protected Routes

**Two layers** — both needed for security in depth:

1. **Middleware** (`src/middleware.ts`) — edge-level, redirects unauthenticated users before the page renders. Fast but not 100% reliable for sensitive data (edge cache quirks).

2. **`withAuth` HOC** — server-side, validates the JWT on every request via `supabase.auth.getUser()`. This is the authoritative check.

```typescript
// Add a route to PROTECTED_PATHS in middleware.ts
const PROTECTED_PATHS = ['/dashboard', '/insights', '/patterns']

// And protect the page via getServerSideProps
export const getServerSideProps = withAuth(async (context, user) => {
  return { props: { userId: user.id } }
})
```

---

## State Management

| Data type | Where it lives |
|-----------|---------------|
| Server data (games, analysis, insights) | React Query cache |
| Auth state | Supabase session (cookie) |
| Chat/UI transient state | Zustand store |
| Form state | `react-hook-form` |
| URL-driven state | Next.js router query |

Do not put server data in Zustand. React Query handles caching, background refetch, and invalidation.

---

## PR Checklist (frontend feature)

- [ ] API function in `api.ts` (no raw axios in components).
- [ ] React Query hook created.
- [ ] Component receives props, does not fetch.
- [ ] Page is protected via `withAuth` (if it needs auth).
- [ ] `npm run type-check` passes with zero errors.
- [ ] No `console.log` left in.
- [ ] No `any` types without comment.
- [ ] Grep checks from `review-loops.mdc` pass.
