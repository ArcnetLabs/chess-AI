import { useCallback, useEffect, useState } from 'react';
import { BarChart3, Loader2, X } from 'lucide-react';
import { patternApi } from '@/lib/api';
import type { PlayerPattern } from '@/types/pattern.types';

function trendLabel(trend: string | null | undefined): string | null {
  if (!trend) return null;
  const value = trend.toLowerCase();
  if (['worsening', 'down', 'declining'].includes(value)) return 'Trending worse';
  if (['improving', 'up', 'rising'].includes(value)) return 'Improving';
  if (value.includes('stable') || value === 'flat') return 'Stable';
  return null;
}

function trendTone(trend: string | null | undefined): string {
  const value = (trend ?? '').toLowerCase();
  if (['worsening', 'down', 'declining'].includes(value)) return 'text-[#ffb4ab]';
  if (['improving', 'up', 'rising'].includes(value)) return 'text-[#6ffbbe]';
  return 'text-[#bbcabf]';
}

function categoryLabel(type: string, subtype: string): string {
  const clean = subtype
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
  return clean || type;
}

export function PatternsModal({
  userId,
  onClose,
}: {
  userId: number;
  onClose: () => void;
}) {
  const [patterns, setPatterns] = useState<PlayerPattern[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await patternApi.list(userId, { limit: 50 });
      const sorted = [...list].sort((a, b) => {
        if (a.is_strength !== b.is_strength) return a.is_strength ? 1 : -1;
        return b.occurrence_count - a.occurrence_count;
      });
      setPatterns(sorted);
    } catch {
      setError('Could not load your patterns. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void load();
  }, [load]);

  const strengths = patterns.filter((pattern) => pattern.is_strength);
  const leaks = patterns.filter((pattern) => !pattern.is_strength);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end bg-black/70 p-0 backdrop-blur-sm sm:items-center sm:justify-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Your patterns"
    >
      <div className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-t-2xl border border-[#3c4a42] bg-[#201f1f] p-6 shadow-2xl sm:rounded-xl">
        <div className="mb-6 flex items-start justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-wider text-brand-primary">
              Insights
            </p>
            <h2 className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <BarChart3 className="h-6 w-6 text-brand-primary" /> Your Patterns
            </h2>
            <p className="mt-2 text-sm leading-6 text-[#bbcabf]">
              What your analyzed games reveal — strengths to lean on, leaks to close.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="p-1 text-[#bbcabf] hover:text-[#e5e2e1]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          {loading ? (
            <div className="flex items-center justify-center py-10 text-sm text-[#bbcabf]">
              <Loader2 className="mr-2 h-4 w-4 animate-spin text-brand-primary" /> Loading your
              patterns...
            </div>
          ) : error ? (
            <p className="py-6 text-center text-sm text-brand-error">{error}</p>
          ) : patterns.length === 0 ? (
            <p className="py-10 text-center text-sm leading-6 text-[#bbcabf]">
              No patterns yet. Analyze a batch of games and your pattern profile will fill in
              here — strengths, leaks, and how they trend over time.
            </p>
          ) : (
            <div className="space-y-5">
              {leaks.length > 0 && (
                <section>
                  <p className="mb-2 font-mono text-xs uppercase tracking-wider text-[#bbcabf]">
                    Leaks to close
                  </p>
                  <ul className="space-y-3">
                    {leaks.map((pattern) => (
                      <PatternCard key={pattern.id} pattern={pattern} />
                    ))}
                  </ul>
                </section>
              )}
              {strengths.length > 0 && (
                <section>
                  <p className="mb-2 font-mono text-xs uppercase tracking-wider text-[#bbcabf]">
                    Strengths to lean on
                  </p>
                  <ul className="space-y-3">
                    {strengths.map((pattern) => (
                      <PatternCard key={pattern.id} pattern={pattern} />
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PatternCard({ pattern }: { pattern: PlayerPattern }) {
  const trend = trendLabel(pattern.trend_direction);
  return (
    <li className="rounded-lg border border-[#262626] bg-[#171717] px-4 py-3">
      <p className="flex flex-wrap items-center gap-2 font-mono text-[11px] uppercase tracking-wide text-[#bbcabf]">
        <span className="text-brand-primary">{categoryLabel(pattern.pattern_type, pattern.pattern_subtype)}</span>
        <span className="rounded-full border border-[#3c4a42] px-2 py-0.5">{pattern.severity}</span>
        {trend && <span className={`ml-auto normal-case tracking-normal ${trendTone(pattern.trend_direction)}`}>{trend}</span>}
      </p>
      <p className="mt-1.5 text-sm leading-6 text-[#e5e2e1]">{pattern.pattern_description}</p>
      <p className="mt-1.5 font-mono text-xs text-[#bbcabf]">
        {pattern.occurrence_count} occurrences across {pattern.affected_games_count} games
      </p>
    </li>
  );
}
