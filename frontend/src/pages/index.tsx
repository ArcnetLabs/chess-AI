/**
 * / (landing entry point)
 *
 * The previous implementation hosted a Chess.com username pseudo-login
 * form that created a local user without any real authentication. That
 * model was retired when Supabase Auth became the canonical identity
 * layer (see `docs/architecture/auth-system.md`).
 *
 * Two routes out of this page:
 *
 *   - Authenticated (cookie session readable server-side) → /coach
 *     via SSR redirect.
 *   - Unauthenticated → a tiny client shim that checks the URL FRAGMENT
 *     before going anywhere. Supabase's default magic-link template links
 *     to the site root with the tokens in the fragment (#access_token=...).
 *     Fragments are invisible to the server and destroyed by SSR redirects,
 *     so previously this page 302'd straight to /auth/login and the tokens
 *     were lost — bouncing EVERY magic link to login in every browser.
 *     Now: if the fragment carries a session, forward it (fragment intact)
 *     to /auth/callback, which handles it; otherwise → /auth/login.
 */

import { useEffect } from 'react';
import type { GetServerSideProps } from 'next';
import { useRouter } from 'next/router';
import { getServerUser } from '@/lib/auth/session';

export const getServerSideProps: GetServerSideProps = async (context) => {
  const user = await getServerUser(context.req, context.res);
  if (user) {
    return {
      redirect: { destination: '/coach', permanent: false },
    };
  }
  // Unauthenticated: render the client shim (hash may still hold tokens).
  return { props: {} };
};

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    const hash = window.location.hash;
    if (hash && hash.includes('access_token')) {
      // Full browser navigation — preserves the fragment the server
      // never saw. /auth/callback owns implicit-flow session pickup.
      window.location.replace(`/auth/callback${hash}`);
      return;
    }
    router.replace('/auth/login');
  }, [router]);

  return null;
}
