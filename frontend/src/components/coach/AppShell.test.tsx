import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AppShell } from './AppShell';

const push = vi.fn();

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
  useRouter: () => ({ pathname: '/coach', push }),
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
    },
    loading: false,
    refetchUser: vi.fn(),
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
    expect(within(sidebar).getByText('Drills')).toBeInTheDocument();
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

  it('shows the stale-account path to the analyze onboarding when nothing is analyzed', () => {
    mocks.useCurrentUser.mockReturnValue({
      user: { id: 7, display_name: 'New', chesscom_username: 'new', analyzed_games: 0 },
      loading: false,
      refetchUser: vi.fn(),
    });
    render(
      <AppShell>
        <p>chat body</p>
      </AppShell>,
    );
    const sidebar = screen.getByRole('complementary');
    expect(within(sidebar).getByText('Analyze your games')).toBeInTheDocument();
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
