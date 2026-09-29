import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AppShell } from './AppShell';

const push = vi.fn();
// The onboarding gate redirects with `replace`, so it leaves no history entry to
// bounce back to — a redirect that pushes traps the user in a loop.
const replace = vi.fn();

const mocks = vi.hoisted(() => ({
  useCurrentUser: vi.fn(),
  api: {
    games: { fetchRecent: vi.fn() },
    analysis: { analyzeGames: vi.fn() },
  },
  chatService: {
    setUserId: vi.fn(),
    createSession: vi.fn(),
    listSessions: vi.fn(),
    setSessionId: vi.fn(),
    getHistory: vi.fn(),
    sendMessage: vi.fn(),
  },
}));

vi.mock('next/router', () => ({
  useRouter: () => ({ pathname: '/coach', push, replace, events: { on: vi.fn(), off: vi.fn() } }),
}));

vi.mock('@/hooks', () => ({
  useCurrentUser: mocks.useCurrentUser,
}));

vi.mock('@/lib/api', () => ({ default: mocks.api }));

vi.mock('@/services/chatService', () => ({ default: mocks.chatService }));

import { useChatStore } from '@/store/chatStore';

const initialState = useChatStore.getState();

function resetStore() {
  useChatStore.setState(initialState, true);
  vi.clearAllMocks();
  mocks.useCurrentUser.mockReturnValue({
    user: {
      id: 7,
      display_name: 'Nimzo Regular',
      chesscom_username: 'nimzo',
      chesscom_avatar: 'https://example.com/pic.png',
      // The dashboard is gated on having analysed games, so the default fixture is an
      // account that has some — otherwise every shell test would be measuring the gate.
      analyzed_games: 143,
    },
    loading: false,
    refetchUser: vi.fn(),
  });
}

function userStub(overrides: Record<string, unknown>) {
  const base = mocks.useCurrentUser();
  mocks.useCurrentUser.mockReturnValue({
    ...base,
    user: { ...base.user, ...overrides },
  });
}

describe('AppShell sidebar', () => {
  beforeEach(resetStore);

  it('renders the profile chip with the chess.com avatar and nav items', () => {
    render(
      <AppShell>
        <p>chat body</p>
      </AppShell>,
    );
    const sidebar = screen.getByRole('complementary');
    expect(within(sidebar).getByText('Nimzo Regular')).toBeInTheDocument();
    expect(within(sidebar).getByRole('img')).toHaveAttribute(
      'src',
      'https://example.com/pic.png',
    );
    expect(within(sidebar).getByText('Home')).toBeInTheDocument();
    expect(within(sidebar).getByText('Insights')).toBeInTheDocument();
    expect(within(sidebar).getByText('Patterns')).toBeInTheDocument();
    // "Drills" was renamed: ChessRun prescribes practice, the partners host it.
    expect(within(sidebar).getByText('Practice')).toBeInTheDocument();
    expect(within(sidebar).getByText('Recent Chats')).toBeInTheDocument();
  });

  it('no longer shows the logo wordmark in the sidebar', () => {
    render(
      <AppShell>
        <p>chat body</p>
      </AppShell>,
    );
    const sidebar = screen.getByRole('complementary');
    expect(within(sidebar).queryAllByText(/chess/).length).toBe(0);
  });

  it('gates the dashboard when nothing has been analyzed', () => {
    userStub({ analyzed_games: 0 });
    render(
      <AppShell>
        <p>chat body</p>
      </AppShell>,
    );

    // Refused, not advised: the coach has nothing to say without analysed games, so the
    // dashboard does not render at all and the user is sent to analyse.
    expect(replace).toHaveBeenCalledWith('/onboarding/analyze');
    expect(screen.queryByText('chat body')).not.toBeInTheDocument();
  });

  it('sends an unlinked account to the chess.com step instead', () => {
    userStub({ chesscom_username: null, analyzed_games: 0 });
    render(
      <AppShell>
        <p>chat body</p>
      </AppShell>,
    );

    expect(replace).toHaveBeenCalledWith('/onboarding/link-chesscom');
    expect(screen.queryByText('chat body')).not.toBeInTheDocument();
  });

  it('sends a signed-out visitor to sign in, remembering where they were', () => {
    mocks.useCurrentUser.mockReturnValue({ user: null, loading: false, refetchUser: vi.fn() });
    render(
      <AppShell>
        <p>chat body</p>
      </AppShell>,
    );

    expect(replace).toHaveBeenCalledWith(
      `/auth/login?next=${encodeURIComponent('/coach')}`,
    );
    expect(screen.queryByText('chat body')).not.toBeInTheDocument();
  });

  it('waits for the profile before deciding, so a slow load is not a redirect', () => {
    mocks.useCurrentUser.mockReturnValue({ user: null, loading: true, refetchUser: vi.fn() });
    render(
      <AppShell>
        <p>chat body</p>
      </AppShell>,
    );

    expect(replace).not.toHaveBeenCalledWith(expect.stringContaining('/auth/login'));
  });

  it('starts a new coach chat from the sidebar mode list', async () => {
    mocks.chatService.createSession.mockResolvedValue({
      session_id: 's-new',
      message: 'Welcome to ChessRun.',
    });
    const user = userEvent.setup();
    render(
      <AppShell>
        <p>chat body</p>
      </AppShell>,
    );
    const sidebar = screen.getByRole('complementary');
    await user.click(within(sidebar).getByText('Ask ChessRun'));
    expect(mocks.chatService.createSession).toHaveBeenCalledWith(7, 'coach');
    expect(push).toHaveBeenCalledWith('/coach');
  });
});
