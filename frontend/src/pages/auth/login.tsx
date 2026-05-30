/**
 * /auth/login
 *
 * Passwordless sign-in per FR-AUTH-1: email + Chess.com username only.
 * Sends a Supabase magic link; session is established in /auth/callback.
 */

import { useState, type FormEvent } from 'react'
import { useRouter } from 'next/router'
import { createClient } from '@/lib/supabase/client'
import { getAuthCallbackUrl } from '@/lib/auth/site-url'

function normalizeChesscomUsername(raw: string): string {
  return raw.trim().toLowerCase()
}

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [chesscomUsername, setChesscomUsername] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [linkSent, setLinkSent] = useState(false)

  const queryError =
    typeof router.query.error === 'string' ? router.query.error : null

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    const username = normalizeChesscomUsername(chesscomUsername)
    if (username.length < 3) {
      setError('Chess.com username must be at least 3 characters.')
      setLoading(false)
      return
    }

    const supabase = createClient()
    const redirectTo = getAuthCallbackUrl()

    const { error: otpError } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: {
        shouldCreateUser: true,
        emailRedirectTo: redirectTo,
        data: {
          chesscom_username: username,
        },
      },
    })

    if (otpError) {
      setError(otpError.message)
      setLoading(false)
      return
    }

    setLinkSent(true)
    setLoading(false)
  }

  if (linkSent) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background p-4">
        <div className="w-full max-w-sm space-y-4 text-center">
          <h1 className="text-2xl font-bold tracking-tight">Check your email</h1>
          <p className="text-sm text-muted-foreground">
            We sent a sign-in link to <strong>{email.trim()}</strong>. Click it to
            open ChessIQ — no password required.
          </p>
          <p className="text-xs text-muted-foreground">
            Chess.com username <strong>{normalizeChesscomUsername(chesscomUsername)}</strong>{' '}
            will be linked when you continue.
          </p>
        </div>
      </main>
    )
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight">Get started with ChessIQ</h1>
          <p className="text-sm text-muted-foreground">
            Enter your email and Chess.com username. We&apos;ll email you a secure
            sign-in link — no password to remember.
          </p>
        </div>

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
            <label htmlFor="chesscom_username" className="text-sm font-medium">
              Chess.com username
            </label>
            <input
              id="chesscom_username"
              type="text"
              autoComplete="username"
              required
              minLength={3}
              value={chesscomUsername}
              onChange={(e) => setChesscomUsername(e.target.value)}
              placeholder="e.g. gh_wilder"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          {(error || queryError) && (
            <p className="text-sm text-destructive">{error || queryError}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity disabled:opacity-50"
          >
            {loading ? 'Sending link…' : 'Email me a sign-in link'}
          </button>
        </form>
      </div>
    </main>
  )
}
