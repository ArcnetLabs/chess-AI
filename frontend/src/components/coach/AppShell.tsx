import { useRouter } from 'next/router';
import { useState, type ReactNode } from 'react';
import {
  BarChart3,
  Brain,
  ChevronDown,
  Dumbbell,
  Loader2,
  MessageSquare,
  MessageSquarePlus,
  Search,
  Sparkles,
} from 'lucide-react';
import { useCurrentUser } from '@/hooks';
import { useChatStore } from '@/store/chatStore';
import type { ChatMode } from './chatMode';


const NAV_ITEMS = [
  { href: '/coach', label: 'Home', icon: MessageSquare },
  { href: '/coach/insights', label: 'Insights', icon: Brain },
  { href: '/coach/patterns', label: 'Patterns', icon: BarChart3 },
  { href: '/coach/training', label: 'Drills', icon: Dumbbell },
] as const;

const MODE_OPTIONS: Array<{ mode: ChatMode; label: string; icon: typeof MessageSquarePlus }> = [
  { mode: 'coach', label: 'New Chat', icon: MessageSquarePlus },
  { mode: 'analyze', label: 'New Analyze Chat', icon: Search },
  { mode: 'interview', label: 'New Interview', icon: Sparkles },
];

export function ProfileChip() {
  const { user } = useCurrentUser();
  if (!user) {
    return (
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-full bg-[#2a2a2a]" />
        <span className="h-4 w-24 rounded bg-[#2a2a2a]" />
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
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-primary/15 font-mono text-sm font-semibold text-brand-primary">
          {initial}
        </div>
      )}
      <span className="truncate text-sm font-medium text-[#e5e2e1]">
        {user.display_name || user.chesscom_username || 'Your profile'}
      </span>
      <ChevronDown className="ml-auto h-4 w-4 shrink-0 text-[#bbcabf]" />
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = router.pathname;
  const { user, loading } = useCurrentUser();
  const initializeSession = useChatStore((state) => state.initializeSession);
  const openSession = useChatStore((state) => state.openSession);
  const sessionId = useChatStore((state) => state.sessionId);
  const recentSessions = useChatStore((state) => state.recentSessions);
  const isRestoringSession = useChatStore((state) => state.isRestoringSession);
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

  const openGameChat = (sessionId: string) => {
    void openSession(sessionId);
    setMobileMenuOpen(false);
    void router.push('/coach');
  };

  const sidebarBody = (
    <nav className="flex min-h-0 flex-1 flex-col">
      <div className="space-y-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
          <button
            key={href}
            type="button"
            onClick={() => {
              void router.push(href);
              setMobileMenuOpen(false);
            }}
            className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
              isActive(href)
                ? 'bg-black/50 font-medium text-[#e5e2e1]'
                : 'text-[#bbcabf] hover:bg-[#1c1c1c] hover:text-[#e5e2e1]'
            }`}
          >
            <Icon
              className={`h-4 w-4 ${isActive(href) ? 'text-brand-primary' : ''}`}
            />
            {label}
          </button>
        ))}
      </div>

      <div className="mt-7 min-h-0 flex-1 overflow-y-auto">
        <button
          type="button"
          onClick={() => setRecentOpen((open) => !open)}
          className="mb-2 flex w-full items-center justify-between px-3 font-mono text-xs uppercase tracking-wider text-[#bbcabf]"
        >
          Recent Chats
          <ChevronDown
            className={`h-3.5 w-3.5 transition-transform ${recentOpen ? 'rotate-180' : ''}`}
          />
        </button>
        {recentOpen && (
          <div className="space-y-1">
            {(recentSessions ?? []).length ? (
              recentSessions.slice(0, 6).map((session) => (
                <button
                  key={session.session_id}
                  type="button"
                  onClick={() => openGameChat(session.session_id)}
                  className={`w-full truncate rounded-md px-3 py-2 text-left text-sm transition-colors ${
                    session.session_id === sessionId
                      ? 'bg-[#1c1c1c] text-[#e5e2e1]'
                      : 'text-[#bbcabf] hover:bg-[#1c1c1c] hover:text-[#e5e2e1]'
                  }`}
                >
                  {session.preview}
                </button>
              ))
            ) : (
              <p className="px-3 text-xs leading-5 text-[#bbcabf]/70">
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
          className="mb-3 flex w-full items-center justify-center gap-2 rounded-lg border border-brand-primary/40 bg-brand-primary/10 px-4 py-2.5 font-mono text-xs text-brand-primary transition-colors hover:bg-brand-primary/20"
        >
          <Sparkles className="h-4 w-4" /> Analyze your games
        </button>
      )}
      <div className="border-t border-[#262626] pt-3">
        <div className="space-y-1">
          {MODE_OPTIONS.map(({ mode, label, icon: Icon }) => (
            <button
              key={mode}
              type="button"
              onClick={() => selectMode(mode)}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm text-[#bbcabf] transition-colors hover:bg-[#1c1c1c] hover:text-[#e5e2e1]"
            >
              <Icon className="h-4 w-4" /> {label}
            </button>
          ))}
        </div>
      </div>
    </nav>
  );

  return (
    <div className="min-h-screen bg-[#0d0d0d] font-sans text-[#e5e2e1]">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[272px] flex-col border-r border-[#1f1f1f] bg-[#111111] p-5 lg:flex">
        <button
          type="button"
          onClick={() => void router.push('/coach')}
          className="rounded-lg p-1 text-left"
          aria-label="Home"
        >
          <ProfileChip />
        </button>
        {sidebarBody}
      </aside>

      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-[#1f1f1f] bg-[#111111] px-4 lg:hidden">
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
          aria-label="Open menu"
          onClick={() => setMobileMenuOpen((open) => !open)}
          className="rounded-md p-2 text-[#bbcabf] hover:bg-[#1c1c1c]"
        >
          <MessageSquare className="h-5 w-5" />
        </button>
      </header>
      {mobileMenuOpen && (
        <div className="fixed inset-x-0 top-14 z-40 max-h-[75vh] overflow-y-auto border-b border-[#1f1f1f] bg-[#111111] p-4 lg:hidden">
          {sidebarBody}
        </div>
      )}

      <main data-app-shell="1" className="lg:pl-[272px]">
        {loading ? (
          <div className="flex min-h-screen items-center justify-center text-[#bbcabf]">
            <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Loading
            your workspace...
          </div>
        ) : !user ? (
          <div className="flex min-h-screen items-center justify-center px-6 text-center text-[#bbcabf]">
            Your coaching workspace could not be loaded.
          </div>
        ) : (
          children
        )}
      </main>
    </div>
  );
}

