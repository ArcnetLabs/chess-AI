import Link from 'next/link';
import { useRouter } from 'next/router';
import React from 'react';

const NAV_LINKS = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/coach', label: 'Coach' },
  { href: '/patterns', label: 'Patterns' },
  { href: '/training', label: 'Training' },
] as const;

interface ChessrunPageShellProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  maxWidth?: 'md' | 'lg' | 'xl' | '7xl';
}

export const ChessrunPageShell: React.FC<ChessrunPageShellProps> = ({
  children,
  title,
  subtitle,
  maxWidth = '7xl',
}) => {
  const router = useRouter();
  const maxClass =
    maxWidth === 'md'
      ? 'max-w-md'
      : maxWidth === 'lg'
        ? 'max-w-lg'
        : maxWidth === 'xl'
          ? 'max-w-xl'
          : 'max-w-7xl';

  return (
    <div className="chessrun-page-bg relative overflow-x-hidden">
      <div
        className="pointer-events-none fixed inset-0 z-0 opacity-20"
        aria-hidden
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_30%,rgba(132,255,0,0.12),transparent_70%)]" />
      </div>
      <div className="fixed top-1/4 -right-24 h-96 w-96 rounded-full bg-brand-primary/10 blur-[128px] pointer-events-none" />
      <div className="relative z-10 flex min-h-screen flex-col">
        <header className="flex items-center justify-between bg-surface-low/80 px-6 py-4 backdrop-blur-md md:px-10">
          <Link href="/dashboard" className="flex items-center gap-2">
            <span className="font-display text-2xl text-brand-primary" aria-hidden>
              ♜
            </span>
            <span className="font-display text-lg font-bold tracking-tight text-content">
              ChessIQ
            </span>
          </Link>
          <nav className="hidden items-center gap-1 sm:flex">
            {NAV_LINKS.map(({ href, label }) => {
              const active = router.pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={`rounded-chess px-3 py-1.5 text-sm font-medium transition-colors ${
                    active
                      ? 'bg-brand-primary/15 text-brand-primary'
                      : 'text-content-muted hover:bg-surface-container hover:text-content'
                  }`}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        </header>
        <main className={`mx-auto w-full flex-1 px-4 py-8 sm:px-6 lg:px-8 ${maxClass}`}>
          {(title || subtitle) && (
            <div className="mb-8">
              {title && (
                <h1 className="font-display text-3xl font-bold tracking-tight text-content md:text-4xl">
                  {title}
                </h1>
              )}
              {subtitle && (
                <p className="mt-2 max-w-2xl text-content-muted">{subtitle}</p>
              )}
            </div>
          )}
          {children}
        </main>
      </div>
    </div>
  );
};
