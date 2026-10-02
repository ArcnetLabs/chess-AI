/**
 * The onboarding reveal has to wait for backend work it cannot see yet.
 *
 * `src/pages/` may not hold test files (Next.js treats every file there as a
 * route — see `src/test/noTestsInPages.test.ts`), so the page is driven from
 * here instead. That matters: `npm test` cannot otherwise see this page at all,
 * and the page's own defect was a *timing* one — the reveal read `patterns` and
 * the profile once, at the moment the analysis job reported `completed`, while
 * the backend queues the final pattern detection 5s behind the last game and the
 * profile snapshot ~60s behind that (267s measured on a 200-game detection
 * pass). The reveal therefore rendered without "Your Superpower", "Your
 * Opportunity" and the profile-summary headline, and /coach/patterns — visited
 * later — showed all three.
 *
 * These tests drive the real page component with fake timers and assert on the
 * props the reveal actually receives, so they cover the refresh schedule itself:
 * first retry at 5s, backoff to a 30s ceiling, give up at the 8-minute budget,
 * stop as soon as both have arrived, and clear the pending retry on unmount.
 */
import { useState } from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  useCurrentUser: vi.fn(),
  usePlayerProfile: vi.fn(),
  useAnalysisStatus: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  api: {
    games: { getForUser: vi.fn(), fetchRecent: vi.fn() },
    patterns: { list: vi.fn() },
    analysis: {
      getActiveJobStatus: vi.fn(),
      getPipelineStatus: vi.fn(),
      analyzeGames: vi.fn(),
    },
  },
}));

vi.mock('@/hooks', () => ({
  useCurrentUser: mocks.useCurrentUser,
  usePlayerProfile: mocks.usePlayerProfile,
  useAnalysisStatus: mocks.useAnalysisStatus,
}));

vi.mock('@/lib/api', () => ({ default: mocks.api }));

vi.mock('next/router', () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock('react-hot-toast', () => ({
  default: { success: mocks.toastSuccess, error: mocks.toastError },
}));

// The reveal itself is a large presentational tree; the contract under test is
// what the page hands it, so surface those props as attributes.
vi.mock('@/components/insights/AnalysisInsights', async () => {
  const React = await import('react');
  return {
    AnalysisInsights: (props: { patterns: unknown[]; profile: unknown }) =>
      React.createElement('div', {
        'data-testid': 'reveal',
        'data-patterns': String(props.patterns.length),
        'data-profile': props.profile ? 'yes' : 'no',
      }),
  };
});

import AnalyzeOnboardingPage from '@/pages/onboarding/analyze';

const USER = { id: 7, chesscom_username: 'testplayer', analyzed_games: 200 };
const ANALYZED_GAME = {
  id: 1,
  is_analyzed: true,
  analysis: { accuracy_percentage: 82.5 },
};
const PATTERN = { id: 1, pattern_type: 'hanging_piece', name: 'Hanging pieces' };
const PROFILE = { id: 1, user_id: 7, profile_version: 1 };

/** Flipped by a test to stand for the deferred backend work landing. */
let patternsAvailable: boolean;
let profileAvailable: boolean;

/** The reveal props, as the page rendered them. */
function revealPatterns(): string | null {
  return screen.getByTestId('reveal').getAttribute('data-patterns');
}

function apiCalls(): number {
  return mocks.api.games.getForUser.mock.calls.length;
}

async function flush(turns = 30) {
  await act(async () => {
    for (let i = 0; i < turns; i += 1) {
      await Promise.resolve();
    }
  });
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

/**
 * Render the page and take it to the reveal: the button starts the run, the
 * mocked job reports `completed` immediately (as the real one does, the moment
 * the last game is persisted), and the first `loadResults` paints the reveal
 * from what exists *right then* — no patterns, no profile.
 */
async function renderReveal() {
  const view = render(<AnalyzeOnboardingPage />);
  fireEvent.click(screen.getByRole('button', { name: /analyze my games/i }));
  await flush();
  return view;
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] });
  patternsAvailable = false;
  profileAvailable = false;

  mocks.useCurrentUser.mockReturnValue({
    user: USER,
    loading: false,
    refetchUser: vi.fn(),
  });

  mocks.usePlayerProfile.mockImplementation(() => {
    const [data, setData] = useState<unknown>(undefined);
    return {
      data,
      refetch: async () => {
        if (profileAvailable) setData(PROFILE);
        return { data };
      },
    };
  });

  mocks.useAnalysisStatus.mockReturnValue({
    watchJob: (_jobId: string, options: { onComplete?: () => void }) => {
      options?.onComplete?.();
    },
    error: null,
    status: null,
    isTracking: false,
  });

  mocks.api.games.getForUser.mockResolvedValue([ANALYZED_GAME]);
  mocks.api.games.fetchRecent.mockResolvedValue({
    analysis_queue: { job_id: 'job-1', games_queued: 1, games_skipped_no_moves: 0 },
  });
  mocks.api.patterns.list.mockImplementation(async () =>
    patternsAvailable ? [PATTERN] : [],
  );
  mocks.api.analysis.getActiveJobStatus.mockResolvedValue(null);
  mocks.api.analysis.getPipelineStatus.mockResolvedValue({});
  mocks.api.analysis.analyzeGames.mockResolvedValue({ games_queued: 0 });
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe('the onboarding reveal waits for the pattern list and the profile', () => {
  it('renders the reveal with neither, as the dropped read did', async () => {
    await renderReveal();

    expect(revealPatterns()).toBe('0');
    expect(screen.getByTestId('reveal')).toHaveAttribute('data-profile', 'no');
    expect(apiCalls()).toBe(1);
  });

  it('re-reads on the 5s first retry and stops once both have arrived', async () => {
    await renderReveal();
    expect(toastCalls()).toBe(1);

    // The deferred chain lands while the player is reading the reveal.
    patternsAvailable = true;
    profileAvailable = true;

    await advance(5_000);

    expect(revealPatterns()).toBe('1');
    expect(screen.getByTestId('reveal')).toHaveAttribute('data-profile', 'yes');
    const whenComplete = apiCalls();
    expect(whenComplete).toBeGreaterThan(1);
    // A background pass is silent: no second "Your games are analyzed".
    expect(toastCalls()).toBe(1);

    // Nothing left to wait for — no polling behind the reveal.
    await advance(10 * 60_000);
    expect(apiCalls()).toBe(whenComplete);
  });

  it('keeps polling on a backoff when the data is still missing', async () => {
    await renderReveal();

    await advance(5_000);
    expect(apiCalls()).toBe(2);
    // Second retry is 10s later, the next 20s, then the 30s ceiling.
    await advance(10_000);
    expect(apiCalls()).toBe(3);
    await advance(20_000);
    expect(apiCalls()).toBe(4);
    await advance(30_000);
    expect(apiCalls()).toBe(5);
    await advance(30_000);
    expect(apiCalls()).toBe(6);
  });

  it('gives up at the 8-minute budget instead of polling forever', async () => {
    await renderReveal();

    await advance(60_000);
    const whileWaiting = apiCalls();
    expect(whileWaiting).toBeGreaterThanOrEqual(4);

    await advance(9 * 60_000);
    const atBudget = apiCalls();
    expect(atBudget).toBeGreaterThan(whileWaiting);

    await advance(10 * 60_000);
    expect(apiCalls()).toBe(atBudget);
  });

  it('leaves a rendered reveal alone when a background pass fails', async () => {
    await renderReveal();
    mocks.api.games.getForUser.mockRejectedValueOnce(new Error('proxy blip'));

    await advance(5_000);

    // The reveal stays; the failure is not promoted to the error page.
    expect(screen.getByTestId('reveal')).toBeInTheDocument();
    expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument();

    // And the schedule survives it.
    const afterFailure = apiCalls();
    patternsAvailable = true;
    profileAvailable = true;
    await advance(10 * 60_000);
    expect(apiCalls()).toBeGreaterThan(afterFailure);
    expect(revealPatterns()).toBe('1');
  });

  it('clears the pending retry on unmount', async () => {
    const view = await renderReveal();
    const beforeUnmount = apiCalls();

    view.unmount();
    await advance(10 * 60_000);

    expect(apiCalls()).toBe(beforeUnmount);
  });

  it('does not poll before the analysis has been started', async () => {
    render(<AnalyzeOnboardingPage />);

    await advance(10 * 60_000);

    expect(apiCalls()).toBe(0);
  });
});

function toastCalls(): number {
  return mocks.toastSuccess.mock.calls.length;
}
