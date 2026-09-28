import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PatternsModal } from './PatternsModal';
import type { PlayerPattern } from '@/types/pattern.types';

const mocks = vi.hoisted(() => ({
  patternApi: { list: vi.fn() },
}));

vi.mock('@/lib/api', () => ({
  patternApi: mocks.patternApi,
}));

function pattern(overrides: Partial<PlayerPattern>): PlayerPattern {
  return {
    id: 1,
    user_id: 1,
    pattern_type: 'weakness',
    pattern_subtype: 'major_blunder',
    severity: 'high',
    confidence_score: 0.9,
    occurrence_count: 5,
    affected_games_count: 4,
    affected_games_ratio: 0.5,
    pattern_description: 'Recurring pattern: a serious blunder in the middlegame.',
    is_strength: false,
    ...overrides,
  };
}

async function renderWith(patterns: PlayerPattern[]) {
  mocks.patternApi.list.mockResolvedValue(patterns);
  render(<PatternsModal userId={1} onClose={() => {}} />);
  // The modal loads on mount; wait for the first card to appear.
  await screen.findByText(patterns[0].pattern_description);
}

describe('PatternsModal player-facing copy', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('never shows the raw context signature', async () => {
    // The exact subtype stored in production, which used to render as
    // "Endgame Technique Failure Endgame|Level|Complex|Triggered".
    await renderWith([
      pattern({
        pattern_subtype: 'endgame_technique_failure__endgame|level|complex|triggered',
        pattern_description:
          "Recurring pattern: an endgame technique error in the endgame with level material.",
      }),
    ]);

    expect(screen.getByText('Endgame Technique Failure')).toBeTruthy();
    expect(document.body.textContent).not.toContain('endgame|level|complex|triggered');
    expect(document.body.textContent).not.toContain('|level|');
  });

  it('translates severity into plain words instead of internal tokens', async () => {
    await renderWith([pattern({ severity: 'critical' })]);

    expect(screen.getByText('Costly')).toBeTruthy();
    expect(screen.queryByText('critical')).toBeNull();
  });

  it('hides severity on a strength, which the heading already states', async () => {
    await renderWith([
      pattern({
        is_strength: true,
        severity: 'low',
        pattern_description: 'Strength: your endgame play holds up.',
      }),
    ]);

    expect(screen.queryByText('Minor')).toBeNull();
    expect(screen.getByText('Held up in 4 games')).toBeTruthy();
  });

  it('describes counts the way a player would', async () => {
    await renderWith([pattern({ occurrence_count: 29, affected_games_count: 18 })]);

    expect(screen.getByText('Happened 29 times in 18 games')).toBeTruthy();
    expect(document.body.textContent).not.toContain('occurrences');
  });

  it('shows the trend values the backend actually stores', async () => {
    await renderWith([
      pattern({ id: 1, trend_direction: 'persistent', pattern_description: 'Keeps coming back.' }),
      pattern({ id: 2, trend_direction: 'resolved', pattern_description: 'Stopped happening.' }),
      pattern({ id: 3, trend_direction: 'new', pattern_description: 'Only recently.' }),
    ]);

    expect(screen.getByText('Keeps happening')).toBeTruthy();
    expect(screen.getByText('Not seen lately')).toBeTruthy();
    expect(screen.getByText('New')).toBeTruthy();
  });

  it('says nothing about direction when there is not enough history', async () => {
    // The backend stores NULL when a half of the timeline is too thin to compare.
    await renderWith([pattern({ trend_direction: null })]);

    expect(screen.queryByText(/Keeps happening|Trending worse|Improving|Stable/)).toBeNull();
  });
});
