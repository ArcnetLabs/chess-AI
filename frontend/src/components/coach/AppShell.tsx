import { useRouter } from 'next/router';
import { useState } from 'react';
import {
  BarChart3,
  Brain,
  ChevronDown,
  ChevronLeft,
  Dumbbell,
  Home,
  Loader2,
  PenLine,
  Search,
} from 'lucide-react';
import { useCurrentUser } from '@/hooks';
import { useChatStore } from '@/store/chatStore';
import { KnightGlyph } from '@/components/brand/ChessRunMark';
import type { ChatMode } from './chatMode';

const NAV_ITEMS = [
  { href: '/coach', label: 'Home', icon: Home },
  { href: '/coach/insights', label: 'Insights', icon: Brain },
  { href: '/coach/patterns', label: 'Patterns', icon: BarChart3 },
  { href: '/coach/training', label: 'Drills', icon: Dumbbell },
] as const;

const MODE_OPTIONS: Array<{ mode: ChatMode; label: string }> = [
  { mode: 'coach', label: 'New Chat' },
  { mode: 'analyze', label: 'New Analyze Chat' },
  { mode: 'interview', label: 'New Interview' },
];

export function ProfileChip() {
  const { user } = useCurrentUser();
  if (!user) {
    return (
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-full bg-surface-bright/60" />
        <span className="h-4 w-24 rounded-full bg-surface-bright/50" />
      </div>
    );
  }
  const initial = (user.display_name || user.chesscom_username || 'P')
    .trim()
    .charAt(0)
    .toUpperCase();
  return (
    <div className="flex min-w-0 items-center gap-3">
      {user.chesscom_avatar ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={user.chesscom_avatar}
          alt={`${user.display_name || 'Profile'} avatar`}
          className="h-9 w-9 rounded-full object-cover"
        />
      ) : (
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-primary/15 text-sm font-semibold text-brand-primary">
          {initial}
        </div>
      )}
      <span className="truncate text-[15px] font-semibold text-content">
        {user.display_name || user.chesscom_username || 'Your profile'}
      </span>
      <ChevronDown className="h-4 w-4 shrink-0 text-content-muted" />
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = router.pathname;
  const { user, loading } = useCurrentUser();
  const initializeSession = useChatStore((state) => state.initializeSession);
  const openSession = useChatStore((state) => state.openSession);
  const sessionId = useChatStore((state) => state.sessionId);
  const recentSessionsState = useChatStore(
    (state) => state.recentSessions,
  );
  const recentSessions = (recentSessionsState ?? []) as Array<{ session_id: string; preview: string }>;
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [recentOpen, setRecentOpen] = useState(true);

  function isActive(href: string): boolean {
    if (href === '/coach') return pathname === '/coach';
    return pathname.startsWith(href);
  }

  const selectMode = (mode: ChatMode) => {
    if (!user?.id) return;
    void initializeSession(user.id, mode);
    setMobileMenuOpen(false);
    void router.push('/coach');
  };

  const sidebarBody = (
    <nav className="flex min-h-0 flex-1 flex-col">
      <div className="space-y-1.5">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
          <button
            key={href}
            type="button"
            onClick={() => {
              void router.push(href);
              setMobileMenuOpen(false);
            }}
            className={`flex w-full items-center gap-3.5 rounded-xl px-4 py-3 text-left text-[15px] font-semibold transition-colors ${
              isActive(href)
                ? 'bg-brand-primary/10 text-content'
                : 'text-content-muted hover:bg-surface-bright/25 hover:text-content'
            }`}
          >
            <Icon
              className={`h-[18px] w-[18px] ${isActive(href) ? 'text-brand-primary' : ''}`}
              strokeWidth={isActive(href) ? 2.4 : 2}
            />
            {label}
          </button>
        ))}
      </div>

      <div className="mt-8 min-h-0 flex-1 overflow-y-auto">
        <button
          type="button"
          onClick={() => setRecentOpen((open) => !open)}
          className="mb-2 flex w-full items-center justify-between px-4 text-[15px] font-semibold text-content"
        >
          Recent Chats
          <ChevronDown
            className={`h-4 w-4 text-content-muted transition-transform ${recentOpen ? 'rotate-180' : ''}`}
          />
        </button>
        {recentOpen && (
          <div className="space-y-1">
            {recentSessions.length ? (
              recentSessions.slice(0, 6).map((session) => (
                <button
                  key={session.session_id}
                  type="button"
                  onClick={() => {
                    void openSession(session.session_id);
                    setMobileMenuOpen(false);
                    void router.push('/coach');
                  }}
                  className={`w-full rounded-xl px-4 py-2.5 text-left text-sm leading-5 transition-colors ${
                    session.session_id === sessionId
                      ? 'bg-surface-bright/25 text-content'
                      : 'text-content-muted hover:bg-surface-bright/20 hover:text-content'
                  }`}
                >
                  <span className="line-clamp-2">{session.preview}</span>
                </button>
              ))
            ) : (
              <p className="px-4 text-[13px] leading-5 text-content-muted/60">
                Your coaching conversations appear here.
              </p>
            )}
          </div>
        )}
      </div>

      {user?.analyzed_games === 0 && !loading && (
        <button
          type="button"
          onClick={() => void router.push('/onboarding/analyze')}
          className="mb-3 flex w-full items-center justify-center gap-2 rounded-xl bg-brand-primary/15 px-4 py-3 text-sm font-semibold text-brand-primary transition-colors hover:bg-brand-primary/25"
        >
          Analyze your games
        </button>
      )}

      <button
        type="button"
        onClick={() => selectMode('coach')}
        className="flex items-center justify-between rounded-full bg-surface-container px-2.5 py-2 text-left shadow-brand-ambient transition-colors hover:bg-surface-bright/40"
      >
        <span className="flex items-center gap-2.5">
          <KnightGlyph className="h-7 w-7 text-brand-primary" />
          <span className="text-[15px] font-semibold text-content">Ask ChessRun</span>
        </span>
        <span className="flex h-7 w-7 items-center justify-center rounded-full text-content-muted transition-colors hover:bg-surface-bright/40 hover:text-content">
          <PenLine className="h-3.5 w-3.5" />
        </span>
      </button>
    </nav>
  );

  return (
    <div className="min-h-screen bg-surface font-sans text-content">
      <aside
        data-testid="sidebar"
        className="fixed inset-y-0 left-0 z-40 hidden w-[280px] flex-col bg-surface-dim p-4 lg:flex"
      >
        <div className="mb-6 flex items-center justify-between px-1">
          <button
            type="button"
            onClick={() => void router.push('/coach')}
            className="min-w-0 flex-1 rounded-xl text-left"
            aria-label="Home"
          >
            <ProfileChip />
          </button>
          <span className="ml-2 flex items-center gap-0.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg text-content-muted opacity-50">
              <Search className="h-4 w-4" />
            </span>
            <span
              aria-hidden="true"
              className="flex h-8 w-8 items-center justify-center rounded-lg text-content-muted opacity-50"
            >
              <ChevronLeft className="h-4 w-4" />
            </span>
          </span>
        </div>
        {sidebarBody}
      </aside>

      <header className="sticky top-0 z-30 flex h-14 items-center justify-between bg-surface-dim px-4 lg:hidden">
        <button
          type="button"
          onClick={() => void router.push('/coach')}
          className="flex items-center gap-2"
          aria-label="Home"
        >
          <ProfileChip />
        </button>
        <button
          type="button"
          aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
          onClick={() => setMobileMenuOpen((open) => !open)}
          className={`rounded-lg p-2 ${mobileMenuOpen ? 'text-content' : 'text-content-muted'}`}
        >
          {mobileMenuOpen ? <ChevronLeft className="h-5 w-5" /> : <Search className="h-5 w-5" />}
        </button>
      </header>
      {mobileMenuOpen && (
        <div className="fixed inset-x-0 top-14 z-40 max-h-[75vh] overflow-y-auto bg-surface-dim p-4 lg:hidden">
          {sidebarBody}
        </div>
      )}

      <main data-app-shell="1" className="lg:pl-[280px]">
        {loading ? (
          <div className="flex min-h-screen items-center justify-center text-content-muted">
            <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Loading
            your workspace...
          </div>
        ) : !user ? (
          <div className="flex min-h-screen items-center justify-center px-6 text-center text-content-muted">
            Your coaching workspace could not be loaded.
          </div>
        ) : (
          children
        )}
      </main>
    </div>
  );
}
