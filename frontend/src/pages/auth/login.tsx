/**
 * /auth/login
 *
 * Passwordless sign-in per FR-AUTH-1: email + Chess.com username only.
 * Sends a Supabase magic link; session is established in /auth/callback.
 */

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/router';
import { createClient } from '@/lib/supabase/client';
import { getAuthCallbackUrl } from '@/lib/auth/site-url';

function normalizeChesscomUsername(raw: string): string {
  return raw.trim().toLowerCase();
}

function LoginBackdrop() {
  return (
    <>
      <div
        className="pointer-events-none fixed inset-0 z-0 opacity-20"
        aria-hidden
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(132,255,0,0.15),transparent_70%)]" />
        <div
          className="absolute inset-0 bg-[linear-gradient(to_right,rgba(132,255,0,0.03)_1px,transparent_1px),linear-gradient(to_bottom,rgba(132,255,0,0.03)_1px,transparent_1px)] bg-[size:64px_64px]"
        />
      </div>
      <div className="pointer-events-none fixed top-1/4 -right-24 h-96 w-96 rounded-full bg-brand-primary/10 blur-[128px]" />
      <div className="pointer-events-none fixed bottom-1/4 -left-24 h-96 w-96 rounded-full bg-brand-primary/5 blur-[128px]" />
    </>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [chesscomUsername, setChesscomUsername] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [linkSent, setLinkSent] = useState(false);

  const queryError =
    typeof router.query.error === 'string' ? router.query.error : null;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const username = normalizeChesscomUsername(chesscomUsername);
    if (username.length < 3) {
      setError('Chess.com username must be at least 3 characters.');
      setLoading(false);
      return;
    }

    const supabase = createClient();
    const redirectTo = getAuthCallbackUrl();

    const { error: otpError } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: {
        shouldCreateUser: true,
        emailRedirectTo: redirectTo,
        data: {
          chesscom_username: username,
        },
      },
    });

    if (otpError) {
      setError(otpError.message);
      setLoading(false);
      return;
    }

    setLinkSent(true);
    setLoading(false);
  }

  if (linkSent) {
    return (
      <div className="chessrun-page-bg relative min-h-screen">
        <LoginBackdrop />
        <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6 py-12">
          <div className="w-full max-w-md space-y-6 text-center animate-fade-in">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-chess-md bg-brand-primary/15">
              <span className="text-2xl text-brand-primary" aria-hidden>
                ✉
              </span>
            </div>
            <h1 className="font-display text-3xl font-bold tracking-tight text-content">
              Check your email
            </h1>
            <p className="text-content-muted">
              We sent a sign-in link to{' '}
              <strong className="text-content">{email.trim()}</strong>. Click it to
              open ChessIQ — no password required.
            </p>
            <p className="text-sm text-content-muted">
              Chess.com username{' '}
              <strong className="text-brand-primary">
                {normalizeChesscomUsername(chesscomUsername)}
              </strong>{' '}
              will be linked when you continue.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chessrun-page-bg relative min-h-screen">
      <LoginBackdrop />
      <div className="relative z-10 flex min-h-screen flex-col">
        <header className="flex items-center justify-between bg-surface-low/50 px-6 py-4 backdrop-blur-md md:px-20">
          <div className="flex items-center gap-2">
            <span className="font-display text-2xl text-brand-primary" aria-hidden>
              ♜
            </span>
            <h2 className="font-display text-xl font-bold tracking-tight text-content">
              ChessIQ
            </h2>
          </div>
        </header>

        <main className="flex flex-1 flex-col items-center justify-center px-6 py-12 md:py-24">
          <div className="w-full max-w-md space-y-8">
            <div className="space-y-4 text-center">
              <div className="inline-flex items-center gap-2 rounded-full bg-brand-primary/10 px-3 py-1 text-xs font-bold uppercase tracking-widest text-brand-primary">
                Passwordless sign-in
              </div>
              <h1 className="font-display text-4xl font-bold tracking-tight text-content md:text-5xl">
                Train like a{' '}
                <span className="italic text-brand-primary">Grandmaster</span>
              </h1>
              <p className="text-lg text-content-muted">
                Enter your email and Chess.com username. We&apos;ll send a secure
                magic link — no password to remember.
              </p>
            </div>

            <div className="group relative">
              <div
                className="absolute -inset-0.5 rounded-chess-md bg-brand-primary/20 opacity-20 blur transition duration-500 group-hover:opacity-30"
                aria-hidden
              />
              <form
                onSubmit={handleSubmit}
                className="relative space-y-6 rounded-chess-md bg-surface-container/80 p-8 backdrop-blur-xl"
              >
                <div className="space-y-2">
                  <label
                    htmlFor="email"
                    className="chessrun-label ml-1 flex items-center gap-2"
                  >
                    Email
                  </label>
                  <input
                    id="email"
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="chessrun-input h-12 text-base"
                  />
                </div>

                <div className="space-y-2">
                  <label
                    htmlFor="chesscom_username"
                    className="chessrun-label ml-1 flex items-center gap-2"
                  >
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
                    className="chessrun-input h-12 text-base"
                  />
                </div>

                {(error || queryError) && (
                  <p className="text-sm text-brand-error" role="alert">
                    {error || queryError}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="chessrun-btn-primary flex h-12 w-full items-center justify-center gap-2 text-base"
                >
                  {loading ? 'Sending link…' : 'Email me a sign-in link'}
                </button>
              </form>

              <div className="mt-8 flex items-center justify-center gap-6 text-sm text-content-muted">
                <span className="flex items-center gap-1">Secure</span>
                <span className="flex items-center gap-1">Deep analysis</span>
                <span className="flex items-center gap-1">AI coaching</span>
              </div>
            </div>
          </div>
        </main>

        <footer className="p-8 text-center text-xs uppercase tracking-widest text-content-muted/70">
          © {new Date().getFullYear()} ChessIQ
        </footer>
      </div>
    </div>
  );
}
