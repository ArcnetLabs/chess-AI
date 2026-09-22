/**
 * Browser-independent magic-link confirmation.
 *
 * Supabase's email template sends token_hash and type here. Unlike the PKCE
 * callback, verifyOtp does not depend on verifier state in the browser that
 * originally requested the email.
 *
 * Exception, observed live: when the client requests the link with PKCE (which
 * it must — see lib/supabase/client.ts) the template's token_hash comes through
 * with a `pkce_` prefix, and those tokens cannot be redeemed with verifyOtp at
 * all: POST /auth/v1/verify answers 403 "Email link is invalid or has expired".
 * They are only valid through the hosted verify redirect, which 302s back to
 * /auth/callback?code=... for the client to exchange. The template also passes
 * type=email, which that endpoint rejects with a 500 ("unexpected_failure"), so
 * the type is mapped to the redirect-flow equivalent.
 */

import { useEffect } from 'react'
import { useRouter } from 'next/router'
import { useQueryClient } from '@tanstack/react-query'
import type { EmailOtpType } from '@supabase/supabase-js'
import { createClient } from '@/lib/supabase/client'
import { getAuthCallbackUrl } from '@/lib/auth/site-url'
import { userApi } from '@/lib/api'

/** OTP types the hosted /verify redirect accepts (type=email does not). */
const REDIRECT_OTP_TYPES = new Set([
  'magiclink',
  'signup',
  'invite',
  'recovery',
  'email_change',
])

export default function AuthConfirmPage() {
  const router = useRouter()
  const queryClient = useQueryClient()

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

    // PKCE token: hand it to the hosted verify redirect, which returns a code
    // to /auth/callback for this browser's stored verifier to exchange.
    if (tokenHash.startsWith('pkce_')) {
      const redirectType = REDIRECT_OTP_TYPES.has(type) ? type : 'magiclink'
      const url =
        `${process.env.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/verify` +
        `?token=${encodeURIComponent(tokenHash)}` +
        `&type=${redirectType}` +
        `&redirect_to=${encodeURIComponent(getAuthCallbackUrl())}`
      window.location.replace(url)
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

        // "Registered" = completed the analyze flow before (analyzed_games
        // > 0). Username presence alone is NOT enough: the backend
        // auto-provisions new users with chesscom_username pre-seeded from
        // the signup metadata, which misfiles newcomers as registered.
        try {
          const me = await userApi.me()
          if (me?.chesscom_username && (me.analyzed_games ?? 0) > 0) {
            await queryClient.invalidateQueries({ queryKey: ['me'] })
            router.replace('/coach')
            return
          }
        } catch {
          /* users/me failed — treat as newcomer below */
        }

        const chesscom = data.user?.user_metadata?.chesscom_username
        const requestedNext =
          typeof router.query.next === 'string' ? router.query.next : ''
        const next =
          requestedNext.startsWith('/') && !requestedNext.startsWith('//')
            ? requestedNext
            : '/onboarding/analyze'
        if (typeof chesscom === 'string' && chesscom.trim()) {
          try {
            await userApi.linkChesscom(chesscom.trim().toLowerCase())
            await queryClient.invalidateQueries({ queryKey: ['me'] })
          } catch (linkError) {
            console.warn('[auth/confirm] Chess.com link deferred:', linkError)
            router.replace('/onboarding/link-chesscom')
            return
          }
        } else if (!requestedNext) {
          router.replace('/onboarding/link-chesscom')
          return
        }
        router.replace(next)
      },
    )
  }, [router, router.isReady, router.query])

  return null
}
