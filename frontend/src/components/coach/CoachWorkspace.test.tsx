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

vi.mock('@/lib/api', () => ({
  default: mocks.api,
}));

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

describe('CoachWorkspace (Stanley-style chat surface)', () => {
  beforeEach(resetStore);

  it('renders the Ask ChessRun empty state with starter pills', () => {
    render(<CoachWorkspace />);
    expect(screen.getByText('Ask ChessRun')).toBeInTheDocument();
    expect(screen.getByText('Pattern Recognition')).toBeInTheDocument();
    expect(screen.getByText('Conversion Issues')).toBeInTheDocument();
    expect(screen.getByText('Rating Goals')).toBeInTheDocument();
    expect(screen.getByText('Opening Prep')).toBeInTheDocument();
  });

  it('fills the composer when a starter pill is clicked', async () => {
    const user = userEvent.setup();
    render(<CoachWorkspace />);
    await user.click(screen.getByText('Pattern Recognition'));
    expect(
      (screen.getByPlaceholderText('What would you like to work on today?') as HTMLInputElement)
        .value,
    ).toBe('What patterns do you see in my games?');
  });

  it('opens the analysis modal from the attach button', async () => {
    const user = userEvent.setup();
    render(<CoachWorkspace />);
    await user.click(screen.getByRole('button', { name: 'Attach a game' }));

    expect(await screen.findByText('Connect your games')).toBeInTheDocument();
    expect(screen.getByText('All games')).toBeInTheDocument();
    expect(screen.getByText('30 days')).toBeInTheDocument();
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
    mocks.api.analysis.analyzeGames.mockResolvedValue({
      games_queued: 4,
      job_id: 'job-1',
      status: 'queued',
    });

    render(<CoachWorkspace />);
    await user.click(screen.getByRole('button', { name: 'Attach a game' }));
    await user.click(screen.getByRole('button', { name: 'Run analysis' }));

    expect(mocks.api.games.fetchRecent).toHaveBeenCalledWith(7, { days: 30 });
    expect(mocks.api.analysis.analyzeGames).toHaveBeenCalledWith(7, { days: 30 });
    expect(watchJob).toHaveBeenCalledWith('job-1', expect.any(Object));
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

    const input = screen.getByPlaceholderText('What would you like to work on today?');
    await user.type(input, 'What should I study?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('What should I study?')).toBeInTheDocument();
    expect(await screen.findByText('Let us start with your openings.')).toBeInTheDocument();
    expect(mocks.chatService.sendMessage).toHaveBeenCalledWith(
      'What should I study?',
      undefined,
      7,
    );
  });

  it('renders coach tables as real tables via GFM', async () => {
    const user = userEvent.setup();
    mocks.chatService.listSessions.mockResolvedValue([]);
    mocks.chatService.createSession.mockResolvedValue({
      session_id: 's1',
      message: 'Welcome to ChessRun.',
    });
    mocks.chatService.sendMessage.mockResolvedValue({
      session_id: 's1',
      response: {
        message:
          'What to do instead (pick one):\n\n| Situation | Better than attacking again |\n| --- | --- |\n| You are up material from a gambit | Trade pieces, win the endgame |\n| Your attack failed but position is fine | Improve your worst piece |',
        intent: 'general_question',
        suggestions: [],
        used_llm: true,
        llm_provider: 'local',
        cited_pattern_ids: [],
      },
    });
    useChatStore.setState({ userId: 7 });

    render(<CoachWorkspace />);

    const input = screen.getByPlaceholderText('What would you like to work on today?');
    await user.type(input, 'What now?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    const table = await screen.findByRole('table');
    expect(table).toBeInTheDocument();
    expect(
      screen.getByRole('columnheader', { name: 'Situation' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('cell', { name: 'Trade pieces, win the endgame' }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/\| Situation \|/)).toBeNull();
  });

  it('shows interview baseline prompts in interview mode', () => {
    useChatStore.setState({ sessionMode: 'interview' });
    render(<CoachWorkspace />);
    expect(screen.getByText('Full Baseline')).toBeInTheDocument();
    expect(screen.getByText('Time Budget')).toBeInTheDocument();
    expect(screen.queryByText('Pattern Recognition')).toBeNull();
    expect(screen.getByPlaceholderText("Answer your coach's question...")).toBeInTheDocument();
  });

  it('shows position prompts in analyze mode', () => {
    useChatStore.setState({ sessionMode: 'analyze' });
    render(<CoachWorkspace />);
    expect(screen.getByText('Evaluate A Position')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Paste a FEN or describe the position...')).toBeInTheDocument();
  });

  it('displays a typing indicator while the coach is composing', () => {
    useChatStore.setState({ isTyping: true });
    render(<CoachWorkspace />);
    expect(screen.getByText('Setting things up...')).toBeInTheDocument();
  });
});
