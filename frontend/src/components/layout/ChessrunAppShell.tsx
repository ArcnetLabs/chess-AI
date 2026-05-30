import Link from 'next/link';
import { useRouter } from 'next/router';
import React, { useCallback } from 'react';
import {
  Award,
  Bell,
  HelpCircle,
  LogOut,
  Menu,
  Search,
  Settings,
} from 'lucide-react';
import { createClient } from '@/lib/supabase/client';
import {
  CHESSRUN_MOBILE_NAV,
  CHESSRUN_SIDEBAR_NAV,
  isNavActive,
} from './chessrunNav';

export interface ChessrunAppShellProps {
  children: React.ReactNode;
  /** Hide sidebar headline block on inner pages */
  showEngineBadge?: boolean;
}

function displayRating(user: { current_ratings?: Record<string, unknown> } | undefined): string | null {
  if (!user?.current_ratings || typeof user.current_ratings !== 'object') return null;
  const ratings = user.current_ratings as Record<string, { last?: { rating?: number } }>;
  for (const key of ['chess_rapid', 'chess_blitz', 'chess_bullet']) {
    const r = ratings[key]?.last?.rating;
    if (typeof r === 'number') return String(r);
  }
  return null;
}

export const ChessrunAppShell: React.FC<ChessrunAppShellProps> = ({
  children,
  showEngineBadge = true,
}) => {
  const router = useRouter();
  const pathname = router.pathname;

  const handleLogout = useCallback(async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    await router.push('/auth/login');
  }, [router]);

  return (
    <div className="chessrun-page-bg min-h-screen">
      {/* Top bar */}
      <header className="fixed top-0 z-50 flex h-16 w-full items-center border-none bg-surface px-4 md:px-6">
        <div className="mx-auto flex w-full max-w-screen-2xl items-center justify-between gap-4">
          <div className="flex min-w-0 flex-1 items-center gap-4 md:gap-8">
            <button
              type="button"
              className="text-brand-primary md:hidden"
              aria-label="Open menu"
              onClick={() => {
                const el = document.getElementById('chessrun-sidebar');
                el?.classList.toggle('hidden');
                el?.classList.toggle('flex');
              }}
            >
              <Menu className="h-6 w-6" />
            </button>
            <Link
              href="/dashboard"
              className="shrink-0 font-display text-2xl font-bold tracking-tighter text-brand-primary"
            >
              ChessIQ
            </Link>
            <div className="hidden max-w-xs flex-1 items-center gap-3 rounded-chess-md bg-surface-container px-4 py-2 md:flex lg:max-w-sm">
              <Search className="h-4 w-4 shrink-0 text-content-muted" aria-hidden />
              <input
                type="search"
                placeholder="Search games, players, openings…"
                className="w-full border-none bg-transparent text-sm text-content placeholder:text-content-muted focus:outline-none focus:ring-0"
                disabled
                title="Search coming soon"
              />
            </div>
          </div>
          <div className="flex items-center gap-4 md:gap-6">
            <div className="hidden items-center gap-4 text-content opacity-70 sm:flex">
              <button
                type="button"
                className="transition-colors hover:text-brand-primary"
                aria-label="Notifications"
              >
                <Bell className="h-5 w-5" />
              </button>
              <button
                type="button"
                className="transition-colors hover:text-brand-primary"
                aria-label="Settings"
              >
                <Settings className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Sidebar */}
      <aside
        id="chessrun-sidebar"
        className="fixed left-0 top-0 z-40 hidden h-full w-64 flex-col border-none bg-surface-low pt-20 md:flex"
      >
        {showEngineBadge && (
          <div className="mb-6 px-6">
            <div className="flex items-center gap-3 rounded-chess-md bg-surface-container p-3">
              <Award className="h-5 w-5 text-brand-primary" fill="currentColor" />
              <div>
                <p className="text-[10px] font-medium uppercase tracking-wider text-content/60">
                  Grandmaster
                </p>
                <p className="text-[10px] font-bold uppercase tracking-wider text-brand-primary">
                  Stockfish Engine
                </p>
              </div>
            </div>
          </div>
        )}
        <nav className="flex-1 space-y-1">
          {CHESSRUN_SIDEBAR_NAV.map((item) => {
            const active = isNavActive(pathname, item);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-4 px-6 py-3 text-[10px] font-medium uppercase tracking-wider transition-colors duration-200 ${
                  active
                    ? 'rounded-r-full bg-surface-container text-brand-primary'
                    : 'text-content/60 hover:bg-surface-container hover:text-brand-primary'
                }`}
              >
                <Icon className="h-5 w-5 shrink-0" strokeWidth={1.5} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto space-y-1 px-6 pb-6">
          <Link
            href="/coach"
            className="chessrun-btn-primary mb-4 flex w-full items-center justify-center py-3 text-[10px] uppercase tracking-widest"
          >
            Open Coach
          </Link>
          <button
            type="button"
            className="flex w-full items-center gap-4 py-2 text-[10px] font-medium uppercase tracking-wider text-content/60 transition-colors hover:text-brand-primary"
          >
            <HelpCircle className="h-5 w-5" strokeWidth={1.5} />
            Help
          </button>
          <button
            type="button"
            onClick={() => void handleLogout()}
            className="flex w-full items-center gap-4 py-2 text-[10px] font-medium uppercase tracking-wider text-content/60 transition-colors hover:text-brand-primary"
          >
            <LogOut className="h-5 w-5" strokeWidth={1.5} />
            Logout
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="md:ml-64">
        <main className="mx-auto min-h-screen max-w-screen-2xl px-4 pb-28 pt-20 md:px-6 md:pb-12">
          {children}
        </main>
      </div>

      {/* Mobile bottom nav */}
      <nav className="fixed bottom-0 left-0 z-50 flex w-full items-center justify-around border-t border-brand-primary/10 bg-surface/80 px-2 py-2 backdrop-blur-xl md:hidden">
        {CHESSRUN_MOBILE_NAV.map((item) => {
          const active = isNavActive(pathname, item);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center justify-center rounded-xl p-2 transition-transform active:scale-90 ${
                active
                  ? 'bg-brand-primary text-brand-on-primary'
                  : 'text-content hover:bg-brand-primary/10'
              }`}
            >
              <Icon className="h-5 w-5" strokeWidth={1.5} />
              <span className="text-[10px] font-bold">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
};

/** Profile strip for pages that pass user context into the shell header area */
export function ChessrunProfileStrip({
  displayName,
  subtitle,
  rating,
}: {
  displayName: string;
  subtitle?: string;
  rating?: string | null;
}) {
  return (
    <div className="mb-6 flex items-center justify-end gap-3 border-l border-content-muted/20 pl-6 md:absolute md:right-6 md:top-[4.25rem]">
      <div className="text-right">
        <p className="font-display text-sm font-bold leading-none text-content">{displayName}</p>
        {rating ? (
          <p className="mt-1 text-[10px] font-bold uppercase tracking-widest text-brand-primary">
            Rating: {rating}
          </p>
        ) : (
          subtitle && (
            <p className="mt-1 text-[10px] font-bold uppercase tracking-widest text-brand-primary">
              {subtitle}
            </p>
          )
        )}
      </div>
      <div className="flex h-10 w-10 items-center justify-center rounded-chess-md border border-brand-primary/20 bg-surface-container-highest font-display text-lg text-brand-primary">
        ♜
      </div>
    </div>
  );
}

export { displayRating };
