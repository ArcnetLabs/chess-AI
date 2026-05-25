# Skill: Frontend Implementation

**When to use:** When adding a new page, component, or data-fetching flow to the ChessIQ frontend.

---

## Implementation Order

```
1. API client function (src/lib/api.ts)
   → 2. React Query hook (src/hooks/ or inline)
      → 3. Component or page
         → 4. Types (src/types/index.ts or new type file)
```

Never start with the component. Data flow must be defined first.

---

## Step-by-Step Protocol

### 1. Check for an existing API client function

```bash
rg "export.*<endpoint keyword>" frontend/src/lib/api.ts
```

If it exists, use it. If not, add it to `api.ts` — do not call axios directly from a component.

**Adding to `api.ts`:**
```typescript
// Group by resource — keep consistent with existing patterns
export const patternApi = {
  getPatterns: async (userId: string): Promise<PatternResult[]> => {
    const response = await apiClient.get<PatternResult[]>(`/users/${userId}/patterns`)
    return response.data
  },
  triggerAnalysis: async (userId: string): Promise<{ taskId: string }> => {
    const response = await apiClient.post(`/users/${userId}/patterns/analyze`)
    return response.data
  },
}
```

### 2. Create a React Query hook

Location: `frontend/src/hooks/usePatterns.ts` (create `src/hooks/` if it doesn't exist)

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { patternApi } from '@/lib/api'

export function usePatterns(userId: string) {
  return useQuery({
    queryKey: ['patterns', userId],
    queryFn: () => patternApi.getPatterns(userId),
    enabled: !!userId,
    staleTime: 1000 * 60 * 5, // 5 min — chess patterns don't change per request
  })
}

export function useTriggerPatternAnalysis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => patternApi.triggerAnalysis(userId),
    onSuccess: (_, userId) => {
      queryClient.invalidateQueries({ queryKey: ['patterns', userId] })
    },
  })
}
```

### 3. Implement the page or component

**Page pattern (with auth protection):**
```typescript
// pages/patterns.tsx
import { withAuth } from '@/lib/auth/withAuth'
import { usePatterns } from '@/hooks/usePatterns'

interface Props { userId: string }

export default function PatternsPage({ userId }: Props) {
  const { data: patterns, isLoading, error } = usePatterns(userId)

  if (isLoading) return <div>Loading...</div>
  if (error) return <div>Error loading patterns</div>

  return <PatternList patterns={patterns ?? []} />
}

export const getServerSideProps = withAuth(async (context, user) => {
  return { props: { userId: user.id } }
})
```

**Component pattern:**
```typescript
// components/PatternCard.tsx — pure display, no data fetching
interface PatternCardProps {
  pattern: PatternResult
  onSelect?: (id: string) => void
}

export function PatternCard({ pattern, onSelect }: PatternCardProps) {
  return (
    <div className="rounded-lg border p-4 hover:bg-accent cursor-pointer"
         onClick={() => onSelect?.(pattern.id)}>
      <h3 className="font-semibold">{pattern.name}</h3>
      <p className="text-sm text-muted-foreground">{pattern.description}</p>
    </div>
  )
}
```

---

## Auth Integration Rules

```typescript
// ✅ Protected page — server-side validation before render
export const getServerSideProps = withAuth(async (context, user) => {
  return { props: { userId: user.id } }
})

// ✅ Accessing user in a component (client-side, after page loads)
const supabase = createClient()
const { data: { user } } = await supabase.auth.getUser()

// ❌ Never do this for server-side protection
// getSession() reads the cookie without validating the JWT
const { data: { session } } = await supabase.auth.getSession()
```

## Supabase Data Access (current stage)

At the current architecture stage, **frontend does not query Supabase directly for application data**. All data flows through the FastAPI backend via `src/lib/api.ts`. Supabase is auth-only on the frontend.

When that changes, update this skill and the architecture rule in `.cursor/rules/architecture.mdc`.

---

## Verification

```bash
cd frontend
npm run type-check
npm run lint
```

No `any` types without explanation. No `console.log` in committed code.
