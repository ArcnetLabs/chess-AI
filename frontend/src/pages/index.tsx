/**
 * / (landing entry point)
 *
 * The previous implementation hosted a Chess.com username pseudo-login
 * form that created a local user without any real authentication. That
 * model was retired when Supabase Auth became the canonical identity
 * layer (see `docs/architecture/auth-system.md`).
 *
 * The page is now a thin SSR redirect:
 *   - Authenticated users → /coach
 *   - Unauthenticated users → /auth/login
 *
 * Keeping the redirect server-side means the user never sees a flash of
 * the wrong page and search engines don't index an empty client shell.
 */

import type { GetServerSideProps } from 'next';
import { getServerUser } from '@/lib/auth/session';

export const getServerSideProps: GetServerSideProps = async (context) => {
  const user = await getServerUser(context.req, context.res);
  return {
    redirect: {
      destination: user ? '/coach' : '/auth/login',
      permanent: false,
    },
  };
};

export default function HomePage() {
  // Never rendered — the SSR redirect above runs first.
  return null;
}
