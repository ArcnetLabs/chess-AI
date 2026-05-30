import React from 'react';
import { BarChart3, Sparkles, AlertTriangle } from 'lucide-react';
import type { MoveQualityStats } from '@/types';

interface AnalysisSummaryBento {
  total_games_analyzed?: number;
  accuracy_percentage?: number;
  average_acpl?: number;
  move_quality_breakdown?: MoveQualityStats;
}

interface PerformanceBentoGridProps {
  summary: AnalysisSummaryBento | undefined;
  hasData: boolean;
}

function blundersPerGame(breakdown: MoveQualityStats | undefined, games: number): string {
  if (!breakdown || games <= 0) return '—';
  const blunders = breakdown.blunders ?? 0;
  return (blunders / games).toFixed(1);
}

export const PerformanceBentoGrid: React.FC<PerformanceBentoGridProps> = ({
  summary,
  hasData,
}) => {
  const accuracy = hasData ? (summary?.accuracy_percentage?.toFixed(1) ?? '0') : '—';
  const brilliant = hasData ? String(summary?.move_quality_breakdown?.brilliant_moves ?? 0) : '—';
  const blunderRatio = hasData
    ? blundersPerGame(summary?.move_quality_breakdown, summary?.total_games_analyzed ?? 0)
    : '—';

  const barHeights = hasData
    ? [60, 40, 90, 70, 100]
    : [20, 20, 20, 20, 20];

  return (
    <section className="mb-12 grid grid-cols-1 gap-6 md:grid-cols-3">
      <div className="group relative overflow-hidden bg-surface-low p-8">
        <div className="relative z-10">
          <p className="chessrun-label mb-1">Avg. Accuracy</p>
          <div className="flex items-baseline gap-2">
            <span className="font-display text-6xl font-bold text-content">{accuracy}</span>
            {hasData && <span className="font-display text-xl text-brand-primary">%</span>}
          </div>
          <div className="mt-6 flex h-12 items-end gap-1">
            {barHeights.map((h, i) => (
              <div
                key={i}
                className={`w-full transition-all duration-500 ${
                  i === barHeights.length - 1 && hasData
                    ? 'bg-brand-primary'
                    : 'bg-brand-primary/20 group-hover:bg-brand-primary/30'
                }`}
                style={{ height: `${h}%` }}
              />
            ))}
          </div>
        </div>
        <BarChart3
          className="pointer-events-none absolute -bottom-4 -right-4 h-24 w-24 text-brand-primary opacity-5 transition-opacity group-hover:opacity-10"
          aria-hidden
        />
      </div>

      <div className="group relative overflow-hidden bg-surface-low p-8">
        <div className="relative z-10">
          <p className="chessrun-label mb-1">Brilliant Moves</p>
          <div className="flex items-baseline gap-2">
            <span className="font-display text-6xl font-bold text-brand-secondary">{brilliant}</span>
            {hasData && (
              <span className="chessrun-label text-xs normal-case tracking-tighter">This period</span>
            )}
          </div>
          {hasData && Number(brilliant) > 0 && (
            <div className="mt-6 flex items-center gap-2">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-secondary text-surface"
                  style={{ opacity: 1 - i * 0.2 }}
                >
                  <Sparkles className="h-3 w-3" fill="currentColor" />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="group relative overflow-hidden bg-surface-low p-8">
        <div className="relative z-10">
          <p className="chessrun-label mb-1">Blunder Ratio</p>
          <div className="flex items-baseline gap-2">
            <span className="font-display text-6xl font-bold text-brand-error">{blunderRatio}</span>
            {hasData && blunderRatio !== '—' && (
              <span className="font-display text-xl text-brand-error/80">/game</span>
            )}
          </div>
          <div className="mt-6 h-2 overflow-hidden rounded-full bg-surface-container">
            <div
              className="h-full rounded-full bg-brand-error shadow-[0_0_10px_rgba(255,115,81,0.5)]"
              style={{
                width: hasData
                  ? `${Math.min(100, (Number(blunderRatio) / 3) * 100)}%`
                  : '0%',
              }}
            />
          </div>
          <p className="mt-2 text-right text-[10px] uppercase tracking-widest text-content-muted">
            {hasData ? `ACPL ${summary?.average_acpl?.toFixed(0) ?? '—'}` : 'Analyze games to unlock'}
          </p>
        </div>
        <AlertTriangle
          className="pointer-events-none absolute -bottom-4 -right-4 h-24 w-24 text-brand-error opacity-5"
          aria-hidden
        />
      </div>
    </section>
  );
};
