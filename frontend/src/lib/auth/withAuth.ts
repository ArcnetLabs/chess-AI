import { getServerUser } from '@/lib/auth/session'
import type { User } from '@supabase/supabase-js'
import type {
  GetServerSideProps,
  GetServerSidePropsContext,
  GetServerSidePropsResult,
} from 'next'

type AuthenticatedHandler<P extends Record<string, unknown>> = (
  context: GetServerSidePropsContext,
  user: User,
) => Promise<GetServerSidePropsResult<P>>

interface WithAuthOptions {
  /**
   * Where to send unauthenticated users.
   * The current path is appended as ?next=<pathname> so the login page
   * can redirect back after a successful sign-in.
   * Defaults to '/auth/login'.
   */
  redirectTo?: string
}

/**
 * Wraps a page's getServerSideProps to enforce authentication.
 *
 * Validates the user's JWT on the server before rendering the page.
 * Unauthenticated users are redirected to the login page.
 *
 * The authenticated User object is passed to the handler so pages don't
 * need to repeat the auth check themselves.
 *
 * @example
 * // pages/dashboard.tsx
 * export const getServerSideProps = withAuth(async (context, user) => {
 *   return {
 *     props: {
 *       userId: user.id,
 *       email: user.email ?? '',
 *     },
 *   }
 * })
 *
 * // Pages that need to pass additional server-side props:
 * export const getServerSideProps = withAuth<{ userId: string }>(
 *   async (context, user) => {
 *     const data = await fetchSomeData(user.id)
 *     return { props: { userId: user.id, ...data } }
 *   },
 *   { redirectTo: '/auth/login' },
 * )
 */
export function withAuth<P extends Record<string, unknown>>(
  handler: AuthenticatedHandler<P>,
  options: WithAuthOptions = {},
): GetServerSideProps<P> {
  return async (
    context: GetServerSidePropsContext,
  ): Promise<GetServerSidePropsResult<P>> => {
    const user = await getServerUser(context.req, context.res)

    if (!user) {
      const redirectTo = options.redirectTo ?? '/auth/login'
      const next = context.resolvedUrl
      return {
        redirect: {
          destination: next
            ? `${redirectTo}?next=${encodeURIComponent(next)}`
            : redirectTo,
          permanent: false,
        },
      }
    }

    return handler(context, user)
  }
}
