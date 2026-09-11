/**
 * Browser-independent magic-link confirmation.
 *
 * Supabase's email template sends token_hash and type here. Unlike the PKCE
 * callback, verifyOtp does not depend on verifier state in the browser that
 * originally requested the email.
 */

import { useEffect } from 'react'
import { useRouter } from 'next/router'
import { useQueryClient } from '@tanstack/react-query'
import type { EmailOtpType } from '@supabase/supabase-js'
import { createClient } from '@/lib/supabase/client'
import { userApi } from '@/lib/api'

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

    const supabase = createClient()
    supabase.auth.verifyOtp({ token_hash: tokenHash, type }).then(
      async ({ data, error }) => {
        if (error) {
          console.error('[auth/confirm] verification error:', error.message)
          router.replace(`/auth/login?error=${encodeURIComponent(error.message)}`)
          return
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
