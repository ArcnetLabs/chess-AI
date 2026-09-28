import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import PracticePage from './training';

const mocks = vi.hoisted(() => ({
  useCurrentUser: vi.fn(),
  practice: { getFocus: vi.fn() },
}));

vi.mock('@/hooks', () => ({
  useCurrentUser: mocks.useCurrentUser,
}));

vi.mock('@/lib/api', () => ({
  default: { practice: mocks.practice },
}));

// The shell has its own test; stubbing it here keeps this test about the page's
// own copy and stops a shell change from failing an unrelated assertion.
vi.mock('@/components/coach/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const FOCUS = {
  focus: [
    {
      pattern_id: 119,
      pattern_ids: [119, 137],
      situations: 2,
      focus: 'your endgame technique',
      why: 'It came up in 37% of the 79 times you were in that kind of position, across 18 games.',
      context: 'endgame|level|complex|triggered',
      severity: 'critical',
      trend: 'persistent',
      occurrences: 29,
      opportunities: 79,
      partner: {
        key: 'chessflow',
        name: 'ChessFlow',
        focus: 'guided calculation on the tactical themes you keep meeting',
        status: 'coming_soon',
        url: null,
      },
    },
  ],
  partners: [
    {
      key: 'chessreps',
      name: 'ChessReps',
      focus: 'spaced repetition of your opening repertoire',
      status: 'coming_soon',
      url: null,
    },
    {
      key: 'chessflow',
      name: 'ChessFlow',
      focus: 'guided calculation on the tactical themes you keep meeting',
      status: 'coming_soon',
      url: null,
    },
  ],
};

function renderPage() {
  mocks.useCurrentUser.mockReturnValue({
    user: { id: 1 },
    loading: false,
  });
  return render(<PracticePage />);
}

describe('Practice focus page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.practice.getFocus.mockResolvedValue(FOCUS);
  });

  it('prescribes what to work on with the evidence behind it', async () => {
    renderPage();

    expect(await screen.findByText('your endgame technique')).toBeTruthy();
    expect(
      screen.getByText(/37% of the 79 times you were in that kind of position/),
    ).toBeTruthy();
    expect(screen.getByText('Keeps happening')).toBeTruthy();
  });

  it('says when the same advice covers several situations', async () => {
    renderPage();

    expect(
      await screen.findByText(/You meet it in 2 different kinds of position/),
    ).toBeTruthy();
  });

  it('hands practice off to the partner rather than hosting it', async () => {
    renderPage();

    expect(
      await screen.findByText(/Practise this on ChessFlow/),
    ).toBeTruthy();
  });

  it('does not offer an in-app practice surface', async () => {
    renderPage();
    await screen.findByText('your endgame technique');

    // The product is a coach: no drill to complete here, no progress to chase.
    const text = document.body.textContent ?? '';
    expect(text).not.toMatch(/complete|skip|mark as done|your training plan/i);
    expect(text).not.toMatch(/Coming soon/i);
  });

  it('shows no destination when nothing fits', async () => {
    mocks.practice.getFocus.mockResolvedValue({
      ...FOCUS,
      focus: [{ ...FOCUS.focus[0], partner: null }],
    });
    renderPage();

    expect(
      await screen.findByText(/Bring this into your next session with your coach/),
    ).toBeTruthy();
  });

  it('explains the empty state instead of showing a broken page', async () => {
    mocks.practice.getFocus.mockResolvedValue({ focus: [], partners: FOCUS.partners });
    renderPage();

    expect(await screen.findByText(/Nothing to work on yet/)).toBeTruthy();
  });
});
