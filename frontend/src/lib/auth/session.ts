import { createSupabaseServerClient } from '@/lib/supabase/server'
import type { User } from '@supabase/supabase-js'
import type { IncomingMessage, ServerResponse } from 'http'

/**
 * Retrieve the currently authenticated user from the server.
 *
 * Validates the JWT against Supabase's public keys on every call.
 * Returns null if there is no valid session — never throws.
 *
 * Use this in getServerSideProps or API routes anywhere you need the
 * user identity on the server. Do NOT use getSession() for authorization
 * decisions: it reads the cookie without server-side validation and can
 * be spoofed.
 *
 * @example
 * export const getServerSideProps: GetServerSideProps = async (context) => {
 *   const user = await getServerUser(context.req, context.res)
 *   if (!user) return { redirect: { destination: '/auth/login', permanent: false } }
 *   return { props: { userId: user.id } }
 * }
 */
export async function getServerUser(
  req: Pick<IncomingMessage, 'headers'>,
  res: Pick<ServerResponse, 'appendHeader' | 'setHeader'>,
): Promise<User | null> {
  const supabase = createSupabaseServerClient(req, res)
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser()

  if (error) {
    // AuthSessionMissingError is expected for unauthenticated requests.
    // Other errors (network, JWT malformed) should surface in monitoring.
    if (error.name !== 'AuthSessionMissingError') {
      console.error('[supabase/session] getUser error:', error.message)
    }
    return null
  }

  return user
}
