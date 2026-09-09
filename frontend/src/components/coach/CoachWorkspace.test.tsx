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
  memoryApi: {
    list: vi.fn(),
  },
  trainingApi: {
    listPlans: vi.fn(),
    getActivePlan: vi.fn(),
    createPlan: vi.fn(),
    saveDrill: vi.fn(),
    setDrillStatus: vi.fn(),
    completeDrill: vi.fn(),
    getProgress: vi.fn(),
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
  memoryApi: mocks.memoryApi,
  trainingApi: mocks.trainingApi,
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

  it('opens the analysis flow from the attach button', async () => {
    const user = userEvent.setup();
    render(<CoachWorkspace />);
    await user.click(screen.getByRole('button', { name: 'Attach a game' }));

    expect(await screen.findByRole('dialog', { name: 'Analyze games' })).toBeInTheDocument();
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

  it('renders coach replies as markdown without literal markers', async () => {
    const user = userEvent.setup();
    mocks.chatService.listSessions.mockResolvedValue([]);
    mocks.chatService.createSession.mockResolvedValue({
      session_id: 's1',
      message: 'Welcome to ChessRun.',
    });
    mocks.chatService.sendMessage.mockResolvedValue({
      session_id: 's1',
      response: {
        message: '## Plan\n\n**Keep the gambits** with structure.',
        intent: 'general_question',
        suggestions: [],
        used_llm: true,
        llm_provider: 'local',
        cited_pattern_ids: [],
      },
    });
    useChatStore.setState({ userId: 7 });

    render(<CoachWorkspace />);

    const input = screen.getByPlaceholderText('Ask your coach anything...');
    await user.type(input, 'What now?');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByRole('heading', { name: 'Plan' })).toBeInTheDocument();
    expect(screen.getByText('Keep the gambits')).toBeInTheDocument();
    expect(screen.queryByText(/\*\*/)).toBeNull();
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

    const input = screen.getByPlaceholderText('Ask your coach anything...');
    await user.type(input, 'What now?');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

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

  it('offers a mode picker with the three coaching modes', () => {
    render(<CoachWorkspace />);
    expect(screen.getAllByRole('button', { name: 'New Chat' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: 'New Analyze Chat' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: 'New Interview' }).length).toBeGreaterThan(0);
  });

  it('starts an interview session when the interview mode is selected', async () => {
    const user = userEvent.setup();
    mocks.chatService.listSessions.mockResolvedValue([]);
    mocks.chatService.createSession.mockResolvedValue({
      session_id: 's-interview',
      message: "Let's set your coaching baseline.",
    });

    render(<CoachWorkspace />);
    await user.click(screen.getAllByRole('button', { name: 'New Interview' })[0]);

    expect(mocks.chatService.createSession).toHaveBeenCalledWith(7, 'interview');
    expect(await screen.findByText("Let's set your coaching baseline.")).toBeInTheDocument();
  });

  it('shows interview baseline prompts in interview mode', () => {
    useChatStore.setState({ sessionMode: 'interview' });
    render(<CoachWorkspace />);
    expect(screen.getByText('Full Baseline')).toBeInTheDocument();
    expect(screen.getByText('Time Budget')).toBeInTheDocument();
    expect(screen.queryByText('Pattern Recognition')).toBeNull();
  });

  it('shows position prompts and copy in analyze mode', () => {
    useChatStore.setState({ sessionMode: 'analyze' });
    render(<CoachWorkspace />);
    expect(screen.getByText('Which position should we dig into?')).toBeInTheDocument();
    expect(screen.getByText('Evaluate A Position')).toBeInTheDocument();
  });

  it('adapts the composer placeholder to the session mode', () => {
    useChatStore.setState({ sessionMode: 'interview' });
    render(<CoachWorkspace />);
    expect(screen.getByPlaceholderText("Answer your coach's question...")).toBeInTheDocument();
  });

  it('opens the insights modal and lists what the coach knows', async () => {
    const user = userEvent.setup();
    mocks.memoryApi.list.mockResolvedValue({
      memories: [
        {
          id: 1,
          content_type: 'pattern',
          content_text: 'Opens with the Italian Game as White.',
          content_id: 11,
          metadata: null,
          created_at: null,
          updated_at: '2026-09-09T00:00:00Z',
        },
        {
          id: 2,
          content_type: 'coaching',
          content_text: 'Goal: 1700 rapid.',
          content_id: null,
          metadata: null,
          created_at: null,
          updated_at: '2026-09-09T00:00:00Z',
        },
      ],
      total_count: 2,
      limit: 50,
      offset: 0,
    });

    render(<CoachWorkspace />);
    await user.click(screen.getAllByRole('button', { name: 'What your coach knows' })[0]);

    const dialog = await screen.findByRole('dialog', { name: 'What your coach knows' });
    expect(within(dialog).getByText('Opens with the Italian Game as White.')).toBeInTheDocument();
    expect(within(dialog).getByText('Goal: 1700 rapid.')).toBeInTheDocument();
    expect(within(dialog).getByText('2 memories')).toBeInTheDocument();
    expect(mocks.memoryApi.list).toHaveBeenCalledWith(7, { contentType: undefined, limit: 50 });
  });

  it('filters memories by source when a filter tab is selected', async () => {
    const user = userEvent.setup();
    mocks.memoryApi.list.mockResolvedValue({
      memories: [],
      total_count: 0,
      limit: 50,
      offset: 0,
    });

    render(<CoachWorkspace />);
    await user.click(screen.getAllByRole('button', { name: 'What your coach knows' })[0]);
    const dialog = await screen.findByRole('dialog', { name: 'What your coach knows' });
    await user.click(within(dialog).getByRole('button', { name: 'From Your Games' }));

    expect(mocks.memoryApi.list).toHaveBeenCalledWith(7, { contentType: 'pattern', limit: 50 });

    await user.click(within(dialog).getByRole('button', { name: 'From Our Chats' }));
    expect(mocks.memoryApi.list).toHaveBeenCalledWith(7, { contentType: 'coaching', limit: 50 });
  });

  it('shows the coach-knows empty state when nothing is stored yet', async () => {
    const user = userEvent.setup();
    mocks.memoryApi.list.mockResolvedValue({
      memories: [],
      total_count: 0,
      limit: 50,
      offset: 0,
    });

    render(<CoachWorkspace />);
    await user.click(screen.getAllByRole('button', { name: 'What your coach knows' })[0]);
    const dialog = await screen.findByRole('dialog', { name: 'What your coach knows' });
    expect(within(dialog).getByText(/no saved notes here yet/i)).toBeInTheDocument();
  });

  it('shows the training empty state when no plan exists', async () => {
    const user = userEvent.setup();
    mocks.trainingApi.getProgress.mockResolvedValue({
      total_drills: 0,
      completed_drills: 0,
      pending_drills: 0,
      skipped_drills: 0,
      in_progress_drills: 0,
      completion_rate: 0,
      active_plan_id: null,
      active_plan_version: null,
      active_plan_completion_rate: null,
      by_drill_type: {},
      last_completed_at: null,
    });
    mocks.trainingApi.getActivePlan.mockRejectedValue(new Error('none'));

    render(<CoachWorkspace />);
    await user.click(screen.getAllByRole('button', { name: 'Training' })[0]);
    const dialog = await screen.findByRole('dialog', { name: 'Your training plan' });
    expect(within(dialog).getByText(/No training plan yet/i)).toBeInTheDocument();
  });

  it('lists active plan drills and moves one through start to solved', async () => {
    const user = userEvent.setup();
    mocks.trainingApi.getProgress.mockResolvedValue({
      total_drills: 2,
      completed_drills: 1,
      pending_drills: 1,
      skipped_drills: 0,
      in_progress_drills: 0,
      completion_rate: 50,
      active_plan_id: 3,
      active_plan_version: 2,
      active_plan_completion_rate: 0,
      by_drill_type: {},
      last_completed_at: null,
    });
    mocks.trainingApi.getActivePlan.mockResolvedValue({
      id: 3,
      plan_version: 2,
      status: 'active',
      title: 'Endgame Conversion Focus',
      focus_areas: ['Losing gained material in the middlegame'],
      focus_pattern_ids: [11],
      drill_count: 2,
      completed_drill_count: 0,
      source: 'interview',
      generated_at: '2026-09-09T00:00:00Z',
      drills: [
        {
          id: 71,
          training_plan_id: 3,
          pattern_id: 11,
          drill_type: 'conversion',
          status: 'pending',
          prompt_text: 'Trade into the won rook endgame instead of attacking.',
          position_fen: null,
          expected_answer: null,
          user_answer: null,
          is_correct: null,
          score: null,
          started_at: null,
          completed_at: null,
        },
        {
          id: 72,
          training_plan_id: 3,
          pattern_id: null,
          drill_type: 'tactic',
          status: 'completed',
          prompt_text: 'Spot the fork against the loose knight.',
          position_fen: null,
          expected_answer: null,
          user_answer: null,
          is_correct: true,
          score: null,
          started_at: null,
          completed_at: '2026-09-09T00:00:00Z',
        },
      ],
    });
    mocks.trainingApi.setDrillStatus.mockResolvedValue({
      id: 71,
      training_plan_id: 3,
      pattern_id: 11,
      drill_type: 'conversion',
      status: 'in_progress',
      prompt_text: 'Trade into the won rook endgame instead of attacking.',
      position_fen: null,
      expected_answer: null,
      user_answer: null,
      is_correct: null,
      score: null,
      started_at: '2026-09-09T00:00:01Z',
      completed_at: null,
    });
    mocks.trainingApi.completeDrill.mockResolvedValue({
      id: 71,
      training_plan_id: 3,
      pattern_id: 11,
      drill_type: 'conversion',
      status: 'completed',
      prompt_text: 'Trade into the won rook endgame instead of attacking.',
      position_fen: null,
      expected_answer: null,
      user_answer: 'Trade pieces',
      is_correct: true,
      score: null,
      started_at: '2026-09-09T00:00:01Z',
      completed_at: '2026-09-09T00:00:02Z',
    });

    render(<CoachWorkspace />);
    await user.click(screen.getAllByRole('button', { name: 'Training' })[0]);
    const dialog = await screen.findByRole('dialog', { name: 'Your training plan' });

    expect(within(dialog).getByText('Endgame Conversion Focus')).toBeInTheDocument();
    expect(within(dialog).getByText('Losing gained material in the middlegame')).toBeInTheDocument();
    expect(within(dialog).getByText('Spot the fork against the loose knight.')).toBeInTheDocument();

    await user.click(within(dialog).getByRole('button', { name: 'Start drill' }));
    expect(mocks.trainingApi.setDrillStatus).toHaveBeenCalledWith(7, 71, 'in_progress');
    const input = await within(dialog).findByPlaceholderText('Your answer (optional)...');
    await user.type(input, 'Trade pieces');
    await user.click(within(dialog).getByRole('button', { name: 'Solved' }));

    expect(mocks.trainingApi.completeDrill).toHaveBeenCalledWith(7, 71, {
      user_answer: 'Trade pieces',
      is_correct: true,
    });
  });

  it('skips a pending drill when skip is chosen', async () => {
    const user = userEvent.setup();
    mocks.trainingApi.getProgress.mockResolvedValue({
      total_drills: 1,
      completed_drills: 0,
      pending_drills: 1,
      skipped_drills: 0,
      in_progress_drills: 0,
      completion_rate: 0,
      active_plan_id: 5,
      active_plan_version: 1,
      active_plan_completion_rate: 0,
      by_drill_type: {},
      last_completed_at: null,
    });
    mocks.trainingApi.getActivePlan.mockResolvedValue({
      id: 5,
      plan_version: 1,
      status: 'active',
      title: 'Openings Primer',
      focus_areas: null,
      focus_pattern_ids: null,
      drill_count: 1,
      completed_drill_count: 0,
      source: 'coach',
      generated_at: '2026-09-09T00:00:00Z',
      drills: [
        {
          id: 91,
          training_plan_id: 5,
          pattern_id: null,
          drill_type: 'opening',
          status: 'pending',
          prompt_text: 'Name the gambit line you keep losing against.',
          position_fen: null,
          expected_answer: null,
          user_answer: null,
          is_correct: null,
          score: null,
          started_at: null,
          completed_at: null,
        },
      ],
    });

    render(<CoachWorkspace />);
    await user.click(screen.getAllByRole('button', { name: 'Training' })[0]);
    const dialog = await screen.findByRole('dialog', { name: 'Your training plan' });

    await user.click(within(dialog).getByRole('button', { name: 'Skip' }));
    expect(mocks.trainingApi.setDrillStatus).toHaveBeenCalledWith(7, 91, 'skipped');
  });
});