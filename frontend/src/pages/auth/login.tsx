/**
 * /auth/login
 *
 * Authentication entry point — email/password sign-in.
 *
 * NOTE: Full UI (design, error states, social providers, forgot-password
 * link) is intentionally deferred. This scaffold wires up the Supabase
 * auth flow correctly so it can be styled later without restructuring.
 *
 * Flow:
 *  1. User submits email + password.
 *  2. signInWithPassword() is called on the browser Supabase client.
 *  3. On success, Supabase sets the session cookie (handled by @supabase/ssr).
 *  4. User is pushed to `next` query param or /dashboard.
 *  5. The middleware's "authenticated users skip auth pages" rule prevents
 *     logged-in users from ever reaching this page again.
 *
 * Session persistence:
 *   @supabase/ssr stores the session in cookies (not localStorage) so it
 *   survives page refreshes and is visible to the server. The middleware
 *   silently refreshes expired tokens on every request.
 */

import { useState, type FormEvent } from 'react'
import { useRouter } from 'next/router'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Destination to redirect to after successful sign-in.
  const next =
    typeof router.query.next === 'string' ? router.query.next : '/dashboard'

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    const supabase = createClient()
    const { error } = await supabase.auth.signInWithPassword({ email, password })

    if (error) {
      setError(error.message)
      setLoading(false)
      return
    }

    // Session cookie is now set. The middleware will validate it on the
    // next request. Navigate to the intended destination.
    router.push(next)
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">Sign in to ChessIQ</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label htmlFor="email" className="text-sm font-medium">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="password" className="text-sm font-medium">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity disabled:opacity-50"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="text-center text-sm text-muted-foreground">
          Don&apos;t have an account?{' '}
          <Link href="/auth/signup" className="text-primary underline-offset-4 hover:underline">
            Sign up
          </Link>
        </p>
      </div>
    </main>
  )
}
