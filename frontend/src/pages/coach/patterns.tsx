import { useEffect, useState } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import toast from 'react-hot-toast';
import { AppShell } from '@/components/coach/AppShell';
import api from '@/lib/api';
import { useCurrentUser } from '@/hooks';
import type { PlayerPattern } from '@/types/pattern.types';

export default function PatternsPage() {
  return (
    <AppShell>
      <PatternsBody />
    </AppShell>
  );
}

function topPattern(patterns: PlayerPattern[], strengths: boolean): string {
  const pick = patterns
    .filter((p) => p.is_strength === strengths)
    .sort((a, b) => b.confidence_score - a.confidence_score)[0];
  return pick?.pattern_description ?? '';
}

function PatternsBody() {
  const { user, loading } = useCurrentUser();
  const [patterns, setPatterns] = useState<PlayerPattern[]>([]);
  const [patternsLoading, setPatternsLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);

  useEffect(() => {
    if (!user) return;
    let active = true;
    void (async () => {
      try {
        const list = await api.patterns.list(user.id, { limit: 50 });
        if (active) setPatterns(list);
      } finally {
        if (active) setPatternsLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [user]);

  const strengths = patterns.filter((p) => p.is_strength);
  const weaknesses = patterns.filter((p) => !p.is_strength);

  const triggerAnalysis = async () => {
    if (!user) return;
    setTriggering(true);
    try {
      const response = await api.patterns.triggerAnalysis(user.id);
      toast.success(response.message || 'Analysis queued');
      window.setTimeout(
        () => {
          void api.patterns
            .list(user.id, { limit: 50 })
            .then(setPatterns)
            .catch(() => undefined)
            .finally(() => setTriggering(false));
        },
        6000,
      );
    } catch {
      toast.error('Could not queue a pattern rebuild');
      setTriggering(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface text-content-muted">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Loading patterns...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface">
      <div className="mx-auto max-w-[1100px] px-5 pb-20 pt-6 sm:px-10">
        <header className="mb-8">
          <p className="text-[15px] font-medium text-content">Patterns</p>
        </header>

        <div className="mb-4 flex items-start justify-between">
          <div>
            <p className="text-[22px] font-bold tracking-tight text-content">Your Patterns</p>
            <p className="mt-1 text-sm text-content-muted">
              Repeated behaviors extracted from every analyzed game.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void triggerAnalysis()}
            disabled={triggering}
            className="flex shrink-0 items-center gap-2 rounded-xl bg-surface-container px-4 py-2.5 text-sm font-medium text-content transition-colors hover:bg-surface-bright/50 disabled:opacity-60"
          >
            <RefreshCw className={`h-4 w-4 ${triggering ? 'animate-spin' : ''}`} />
            Rebuild
          </button>
        </div>

        {patternsLoading ? (
          <div className="flex items-center justify-center py-16 text-content-muted">
            <Loader2 className="mr-2 h-4 w-4 animate-spin text-brand-primary" /> Loading pattern
            data...
          </div>
        ) : patterns.length === 0 ? (
          <p className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 px-8 py-14 text-center text-[15px] text-content-muted">
            No patterns yet. Analyze a batch of games and rebuild to populate this page.
          </p>
        ) : (
          <div className="space-y-10">
            {/* reveal cards — 12907 mirror */}
            <div className="grid gap-5 sm:grid-cols-2">
              <RevealCard
                emoji="🔥"
                title="Your Superpower"
                body={topFocus(strengths)}
                fallback="Score lines where you consistently outplay your rating."
                accent
              />
              <RevealCard
                emoji="📈"
                title="Your Opportunity"
                body={topFocus(weaknesses)}
                fallback="The clearest leak costing you points right now."
              />
            </div>

            {strengths.length > 0 && <PatternList title="Strengths" list={strengths} />}
            {weaknesses.length > 0 && <PatternList title="Leaks" list={weaknesses} />}
          </div>
        )}
      </div>
    </div>
  );
}

function topFocus(list: PlayerPattern[]): string {
  if (list.length === 0) return '';
  return list[0].pattern_description;
}

function RevealCard({
  emoji,
  title,
  body,
  fallback,
  accent = false,
}: {
  emoji: string;
  title: string;
  body: string;
  fallback: string;
  accent?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border px-8 py-9 text-center ${
        accent
          ? 'border-brand-primary/20 bg-brand-primary/[0.04]'
          : 'border-surface-bright/30 bg-surface-container/70'
      }`}
    >
      <p className="text-[15px] font-semibold text-content-muted">
        {emoji} {title}
      </p>
      <p className="mx-auto mt-3 max-w-[36ch] text-[22px] font-bold leading-snug tracking-tight text-content">
        {body || fallback}
      </p>
    </div>
  );
}

function PatternList({ title, list }: { title: string; list: PlayerPattern[] }) {
  return (
    <section>
      <h2 className="text-[17px] font-semibold text-content">{title}</h2>
      <ul className="mt-4 space-y-3">
        {list.map((pattern) => (
          <li
            key={pattern.id}
            className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 px-6 py-5"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-md bg-surface-bright/40 px-2 py-0.5 text-[11px] font-semibold text-content-muted">
                {pattern.pattern_type}
                {pattern.pattern_subtype ? ` · ${pattern.pattern_subtype}` : ''}
              </span>
              <span className="text-[11px] text-content-muted">
                {pattern.affected_games_count} games
              </span>
              {pattern.trend_direction && (
                <span className="text-[11px] text-content-muted">
                  trending {pattern.trend_direction}
                </span>
              )}
            </div>
            <p className="mt-2.5 text-[15px] leading-7 text-content">{pattern.pattern_description}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
