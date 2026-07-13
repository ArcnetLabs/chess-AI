/**
 * Browser-independent magic-link confirmation.
 *
 * Supabase's email template sends token_hash and type here. Unlike the PKCE
 * callback, verifyOtp does not depend on verifier state in the browser that
 * originally requested the email.
 */

import { useEffect } from 'react'
import { useRouter } from 'next/router'
import type { EmailOtpType } from '@supabase/supabase-js'
import { createClient } from '@/lib/supabase/client'
import { userApi } from '@/lib/api'

export default function AuthConfirmPage() {
  const router = useRouter()

  useEffect(() => {
    if (!router.isReady) return

    const tokenHash =
      typeof router.query.token_hash === 'string'
        ? router.query.token_hash
        : null
    const type =
      typeof router.query.type === 'string'
        ? (router.query.type as EmailOtpType)
        : null

    if (!tokenHash || !type) {
      router.replace('/auth/login?error=Invalid or incomplete sign-in link.')
      return
    }

    const supabase = createClient()
    supabase.auth.verifyOtp({ token_hash: tokenHash, type }).then(
      async ({ data, error }) => {
        if (error) {
          console.error('[auth/confirm] verification error:', error.message)
          router.replace(`/auth/login?error=${encodeURIComponent(error.message)}`)
          return
        }

        const chesscom = data.user?.user_metadata?.chesscom_username
        if (typeof chesscom === 'string' && chesscom.trim()) {
          try {
            await userApi.linkChesscom(chesscom.trim().toLowerCase())
          } catch (linkError) {
            console.warn('[auth/confirm] Chess.com link deferred:', linkError)
          }
        }

        const requestedNext =
          typeof router.query.next === 'string' ? router.query.next : '/coach'
        const next =
          requestedNext.startsWith('/') && !requestedNext.startsWith('//')
            ? requestedNext
            : '/coach'
        router.replace(next)
      },
    )
  }, [router, router.isReady, router.query])

  return null
}
