import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CoachWorkspace } from './CoachWorkspace';

const mocks = vi.hoisted(() => ({
  useCurrentUser: vi.fn(),
  usePlayerProfile: vi.fn(),
  useAnalysisStatus: vi.fn(),
  useChatSession: vi.fn(),
  chatService: {
    setUserId: vi.fn(),
    createSession: vi.fn(),
    listSessions: vi.fn(),
    setSessionId: vi.fn(),
    getHistory: vi.fn(),
    sendMessage: vi.fn(),
  },
  api: {
    games: { fetchRecent: vi.fn() },
    analysis: { analyzeGames: vi.fn() },
  },
}));

vi.mock('@/hooks', () => ({
  useCurrentUser: mocks.useCurrentUser,
  usePlayerProfile: mocks.usePlayerProfile,
  useAnalysisStatus: mocks.useAnalysisStatus,
  useChatSession: mocks.useChatSession,
}));

vi.mock('@/lib/api', () => ({ default: mocks.api }));

vi.mock('@/services/chatService', () => ({ default: mocks.chatService }));

import { useChatStore } from '@/store/chatStore';

const initialState = useChatStore.getState();

function resetStore() {
  useChatStore.setState(initialState, true);
  vi.clearAllMocks();
  mocks.useCurrentUser.mockReturnValue({
    user: { id: 7, chesscom_username: 'testplayer', analyzed_games: 0 },
    loading: false,
    refetchUser: vi.fn(),
  });
  mocks.usePlayerProfile.mockReturnValue({ data: undefined, refetch: vi.fn() });
  mocks.useAnalysisStatus.mockReturnValue({
    watchJob: vi.fn(),
    cancelJob: vi.fn(),
    status: null,
    isTracking: false,
    error: null,
  });
  mocks.useChatSession.mockReturnValue(undefined);
}

describe('CoachWorkspace', () => {
  beforeEach(resetStore);

  it('shows a loading screen while the user is loading', () => {
    mocks.useCurrentUser.mockReturnValue({ user: null, loading: true });
    const { container } = render(<CoachWorkspace />);
    expect(container.querySelector('.animate-spin')).toBeTruthy();
  });

  it('renders the empty coach state with starter prompts', () => {
    render(<CoachWorkspace />);
    expect(screen.getByText('What should we focus on next?')).toBeInTheDocument();
    expect(screen.getByText('Pattern Recognition')).toBeInTheDocument();
    expect(screen.getByText('Conversion Issues')).toBeInTheDocument();
    expect(screen.getByText('Rating Goals')).toBeInTheDocument();
    expect(screen.getByText('Opening Prep')).toBeInTheDocument();
  });

  it('opens the analysis modal and offers the timeframe options', async () => {
    const user = userEvent.setup();
    render(<CoachWorkspace />);
    await user.click(screen.getAllByRole('button', { name: 'Analyze Games' })[0]);

    const dialog = await screen.findByRole('dialog', { name: 'Analyze games' });
    expect(within(dialog).getByText('Analyze All Games')).toBeInTheDocument();
    expect(within(dialog).getByText('Last 7 Days')).toBeInTheDocument();
    expect(within(dialog).getByText('Last 30 Days')).toBeInTheDocument();
    expect(within(dialog).getByText('This Month')).toBeInTheDocument();
    expect(within(dialog).getByText('Custom Range')).toBeInTheDocument();
  });

  it('sends a message and shows the coach reply', async () => {
    const user = userEvent.setup();
    mocks.chatService.listSessions.mockResolvedValue([]);
    mocks.chatService.createSession.mockResolvedValue({
      session_id: 's1',
      message: 'Welcome to ChessRun.',
    });
    mocks.chatService.sendMessage.mockResolvedValue({
      session_id: 's1',
      response: {
        message: 'Let us start with your openings.',
        intent: 'coaching',
        suggestions: [],
        used_llm: true,
        llm_provider: 'mock',
        cited_pattern_ids: [],
      },
    });
    useChatStore.setState({ userId: 7 });

    render(<CoachWorkspace />);

    const input = screen.getByPlaceholderText('Ask your coach anything...');
    await user.type(input, 'What should I study?');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByText('What should I study?')).toBeInTheDocument();
    expect(await screen.findByText('Let us start with your openings.')).toBeInTheDocument();
    expect(mocks.chatService.sendMessage).toHaveBeenCalledWith(
      'What should I study?',
      undefined,
      7,
    );
  });

  it('starts an analysis job and tracks its progress', async () => {
    const user = userEvent.setup();
    const watchJob = vi.fn();
    mocks.useAnalysisStatus.mockReturnValue({
      watchJob,
      cancelJob: vi.fn(),
      status: null,
      isTracking: false,
      error: null,
    });
    mocks.api.games.fetchRecent.mockResolvedValue({});
    mocks.api.analysis.analyzeGames.mockResolvedValue({ games_queued: 4, job_id: 'job-1' });

    render(<CoachWorkspace />);
    await user.click(screen.getAllByRole('button', { name: 'Analyze Games' })[0]);
    const dialog = await screen.findByRole('dialog', { name: 'Analyze games' });
    await user.click(within(dialog).getByRole('button', { name: 'Start Analysis' }));

    expect(mocks.api.games.fetchRecent).toHaveBeenCalledWith(7, { days: 30 });
    expect(mocks.api.analysis.analyzeGames).toHaveBeenCalledWith(7, { days: 30 });
    expect(watchJob).toHaveBeenCalledWith('job-1', expect.any(Object));
  });
});