/**
 * Analysis insights — the blocks the onboarding reveal (12907/12908) shows
 * after an analysis run, extracted so the coach Insights page renders the very
 * same thing instead of a different summary.
 *
 * `showOnboardingExtras` adds what only belongs to onboarding: the profile
 * silhouette + headline, the "How ChessRun gets you there" trio and the
 * "Grow With ChessRun" CTA.
 */

import { useMemo } from 'react';
import { useRouter } from 'next/router';
import { Brain, LineChart, Search, TrendingUp } from 'lucide-react';
import { KnightGlyph } from '@/components/brand/ChessRunMark';
import type { Game, User } from '@/types';
import type { PlayerProfile } from '@/types/profile.types';
import type { PlayerPattern } from '@/types/pattern.types';

export interface AnalysisInsightsProps {
  /** Games to derive the stats from — the analyzed set, as the reveal uses. */
  games: Game[];
  profile?: PlayerProfile;
  patterns: PlayerPattern[];
  user?: User;
  showOnboardingExtras?: boolean;
}

/** Real, human-readable pattern from the persisted analysis — no filler copy. */
function topPattern(patterns: PlayerPattern[], isStrength: boolean): string | null {
  const match = patterns.find((p) => p.is_strength === isStrength && p.pattern_description);
  return match?.pattern_description ?? null;
}

export function AnalysisInsights({
  games,
  profile,
  patterns,
  user: linkedUser,
  showOnboardingExtras = false,
}: AnalysisInsightsProps) {
  const router = useRouter();

  const stats = useMemo(() => {
    const accs = games
      .map((g) => g.analysis?.accuracy_percentage)
      .filter((a): a is number => a != null);
    const avgAcc = accs.length
      ? Math.round(accs.reduce((a, b) => a + b, 0) / accs.length)
      : null;
    // LOW / AVG / HIGH banding on accuracy an engine-accuracy player feels.
    const band = avgAcc == null ? 1 : avgAcc >= 85 ? 2 : avgAcc >= 75 ? 1 : 0;
    // Win rate from the user's own side of each game.
    const username = linkedUser?.chesscom_username?.toLowerCase();
    const decided = games.filter((g) => g.winner != null);
    const wins = username
      ? decided.filter(
          (g) =>
            (g.winner === 'white' && g.white_username?.toLowerCase() === username) ||
            (g.winner === 'black' && g.black_username?.toLowerCase() === username),
        ).length
      : 0;
    const winRate = decided.length ? Math.round((wins / decided.length) * 100) : null;
    return { avgAcc, band, count: games.length, winRate };
  }, [games, linkedUser]);

  const projected = useMemo(() => {
    // +90 / +180 / +270 rating points across 90 days, scaled by accuracy band.
    return [90, 180, 270][stats.band] ?? 120;
  }, [stats.band]);

  return (
    <div className="space-y-10">
      {showOnboardingExtras && (
        <div className="space-y-6 text-center">
          <div className="mx-auto h-20 w-20 overflow-hidden rounded-full border border-surface-bright/40 bg-surface-container shadow-brand-ambient">
            <PersonSilhouette />
          </div>
          <h1 className="mx-auto max-w-[44rem] text-[24px] font-bold leading-[1.5] tracking-tight text-content sm:text-[27px]">
            {profile?.profile_summary
              ? profile.profile_summary
              : `You analyzed ${stats.count} game${stats.count === 1 ? '' : 's'} — your coach now sees how you actually play.`}
          </h1>
        </div>
      )}

      {/* main stat grid (12907) */}
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 p-7">
          <p className="text-[15px] text-content-muted">Accuracy Rate</p>
          <p className="mt-1 flex items-baseline gap-2">
            <span className="text-[40px] font-bold leading-none tracking-tight text-content">
              {stats.avgAcc != null ? `${stats.avgAcc}%` : '—'}
            </span>
          </p>
          <div className="mt-7">
            <div className="flex justify-between text-[11px] font-semibold uppercase tracking-wider text-content-muted">
              <span>LOW</span>
              <span>AVG</span>
              <span>HIGH</span>
            </div>
            <div className="relative mt-2 h-1.5 rounded-full bg-surface-bright/40">
              <div
                className="absolute top-1/2 h-3.5 w-3.5 -translate-y-1/2 rounded-full border-2 border-surface bg-brand-primary"
                style={{ left: stats.band === 2 ? '85%' : stats.band === 1 ? '50%' : '15%' }}
              />
            </div>
            <p className="mt-3 text-sm font-bold text-content">
              {stats.band === 2
                ? 'High accuracy'
                : stats.band === 1
                  ? 'Average accuracy'
                  : 'Below-average accuracy'}
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 p-7">
          <div className="flex items-center justify-between">
            <p className="text-[15px] text-content-muted">Projected rating growth</p>
            <TrendingUp className="h-4 w-4 text-brand-primary" />
          </div>
          <p className="mt-1 text-[40px] font-bold leading-none tracking-tight text-content">
            +{projected}
          </p>
          <GrowthSketch />
          <div className="mt-2 flex justify-between text-xs text-content-muted">
            <span>Today</span>
            <span>+30d</span>
            <span>+90d</span>
          </div>
        </div>
      </div>

      {/* small stat cards (12907) */}
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 px-7 py-6">
          <p className="text-[15px] text-content-muted">Games analyzed</p>
          <p className="mt-1 text-[36px] font-bold leading-none tracking-tight text-content">
            {stats.count}
          </p>
          <p className="mt-3 text-[13px] leading-5 text-content-muted">
            Analysis ran on your {stats.count} most recent{stats.count === 200 ? ' (at the cap)' : ''}{' '}
            games. Full-history analysis is part of{' '}
            <button
              type="button"
              onClick={() => void router.push('/coach/billing')}
              className="font-semibold text-brand-primary underline underline-offset-2 hover:opacity-90"
            >
              ChessRun Pro
            </button>
            .
          </p>
        </div>
        <div className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 px-7 py-6">
          <p className="text-[15px] text-content-muted">Win rate</p>
          <p className="mt-1 text-[36px] font-bold leading-none tracking-tight text-content">
            {stats.winRate != null ? `${stats.winRate}%` : '—'}
          </p>
        </div>
      </div>

      {/* live profile ratings cross-check (rapid / blitz / bullet / daily) */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {(
          [
            ['Rapid', 'chess_rapid'],
            ['Blitz', 'chess_blitz'],
            ['Bullet', 'chess_bullet'],
            ['Daily', 'chess_daily'],
          ] as const
        ).map(([label, key]) => {
          const rating = (linkedUser?.current_ratings as Record<string, any> | undefined)?.[key]
            ?.last?.rating;
          return (
            <div
              key={key}
              className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 px-5 py-5 text-center"
            >
              <p className="text-[13px] font-semibold text-content-muted">{label}</p>
              <p className="mt-1 text-[28px] font-bold leading-none tracking-tight text-content">
                {typeof rating === 'number' ? rating : '—'}
              </p>
              <p className="mt-1 text-[11px] text-content-muted/70">live from profile</p>
            </div>
          );
        })}
      </div>

      {/* superpower / opportunity (12907) — real persisted patterns only */}
      {(topPattern(patterns, true) || topPattern(patterns, false)) && (
        <div className="grid gap-5 sm:grid-cols-2">
          {topPattern(patterns, true) && (
            <div className="rounded-2xl border border-brand-primary/20 bg-brand-primary/[0.04] px-8 py-9 text-center">
              <p className="text-[15px] font-semibold text-content-muted">🔥 Your Superpower</p>
              <p className="mx-auto mt-3 max-w-[34ch] text-[22px] font-bold leading-snug tracking-tight text-content">
                {topPattern(patterns, true)}
              </p>
            </div>
          )}
          {topPattern(patterns, false) && (
            <div className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 px-8 py-9 text-center">
              <p className="text-[15px] font-semibold text-content-muted">📈 Your Opportunity</p>
              <p className="mx-auto mt-3 max-w-[34ch] text-[22px] font-bold leading-snug tracking-tight text-content">
                {topPattern(patterns, false)}
              </p>
            </div>
          )}
        </div>
      )}

      {showOnboardingExtras && (
        <>
          {/* how ChessRun gets you there (12908) */}
          <div className="space-y-6 text-center">
            <KnightGlyph className="mx-auto h-9 w-9 text-brand-primary" />
            <h2 className="text-[22px] font-bold tracking-tight text-content">
              How ChessRun gets you there
            </h2>
            <div className="grid gap-4 sm:grid-cols-3">
              <HowStep
                icon={Search}
                label="Connect"
                body="Public Chess.com game history — no passwords, ever."
              />
              <HowStep icon={Brain} label="Analyze" body="Engine eval on every single move you make." />
              <HowStep icon={LineChart} label="Coach" body="A coach grounded in your games, 24/7." />
            </div>
          </div>

          {/* CTA (12908) */}
          <button
            type="button"
            onClick={() => void router.push('/coach')}
            className="w-full rounded-full bg-brand-primary px-6 py-5 text-[18px] font-semibold text-brand-on-primary shadow-brand-glow transition-opacity hover:opacity-90"
          >
            Grow With ChessRun
          </button>
        </>
      )}
    </div>
  );
}

/** Neutral empty-person portrait for users without a linked profile picture. */
function PersonSilhouette() {
  return (
    <svg viewBox="0 0 80 80" className="h-full w-full" aria-hidden="true">
      <rect width="80" height="80" fill="#1f2733" />
      <circle cx="40" cy="30" r="13" fill="#5b6b80" />
      <path d="M14 74 Q14 50 40 50 Q66 50 66 74 Z" fill="#5b6b80" />
    </svg>
  );
}

function HowStep({ icon: Icon, label, body }: { icon: typeof Search; label: string; body: string }) {
  return (
    <div className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 px-6 py-7 text-center">
      <span className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-brand-primary/12">
        <Icon className="h-5 w-5 text-brand-primary" />
      </span>
      <p className="mt-3 text-[15px] font-bold text-content">{label}</p>
      <p className="mt-1.5 text-[13px] leading-5 text-content-muted">{body}</p>
    </div>
  );
}

function GrowthSketch() {
  // lightweight projection sketch of the 12907 growth chart
  return (
    <div className="mt-4">
      <svg viewBox="0 0 240 96" className="w-full" aria-hidden="true">
        <defs>
          <linearGradient id="growthFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4edea3" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#4edea3" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path
          d="M4 84 C60 80 110 70 150 50 C185 33 215 22 236 14"
          fill="none"
          stroke="#4edea3"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <path
          d="M4 84 C60 80 110 70 150 50 C185 33 215 22 236 14 L236 96 L4 96 Z"
          fill="url(#growthFill)"
        />
        <circle cx="4" cy="84" r="3" fill="#4edea3" />
        <circle cx="236" cy="14" r="3" fill="#4edea3" />
      </svg>
    </div>
  );
}
