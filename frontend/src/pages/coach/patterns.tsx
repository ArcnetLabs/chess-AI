import { useEffect, useState } from 'react';
import { BarChart3, Loader2, RefreshCw } from 'lucide-react';
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

  const triggerAnalysis = async () => {
    if (!user) return;
    setTriggering(true);
    try {
      const response = await api.patterns.triggerAnalysis(user.id);
      toast.success(response.message || 'Analysis queued');
      // Patterns refresh when the rebuild completes; poll once after a beat.
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
      <div className="flex min-h-screen items-center justify-center text-[#bbcabf]">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Loading patterns...
      </div>
    );
  }

  const strengths = patterns.filter((p) => p.is_strength);
  const weaknesses = patterns.filter((p) => !p.is_strength);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-8">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-brand-primary">
            <BarChart3 className="h-4 w-4" /> Patterns
          </p>
          <h1 className="mt-1 font-display text-3xl font-bold tracking-tight">Your patterns</h1>
          <p className="mt-2 text-sm text-[#bbcabf]">
            Repeated behaviors extracted from every analyzed game — your strengths to keep, and
            your leaks to fix.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void triggerAnalysis()}
          disabled={triggering}
          className="flex shrink-0 items-center gap-2 rounded-xl border border-[#262626] bg-[#141414] px-4 py-2.5 text-sm text-[#bbcabf] transition-colors hover:text-[#e5e2e1] disabled:opacity-60"
        >
          <RefreshCw className={`h-4 w-4 ${triggering ? 'animate-spin' : ''}`} />
          Rebuild
        </button>
      </header>

      {patternsLoading ? (
        <div className="mt-10 flex items-center justify-center py-10 text-[#bbcabf]">
          <Loader2 className="mr-2 h-4 w-4 animate-spin text-brand-primary" /> Loading pattern
          data...
        </div>
      ) : patterns.length === 0 ? (
        <p className="mt-10 rounded-2xl border border-[#262626] bg-[#141414] px-6 py-10 text-center text-sm text-[#bbcabf]">
          No patterns yet. Analyze a batch of games and rebuild to populate this page.
        </p>
      ) : (
        <div className="mt-8 space-y-10">
          <PatternSection title="🔥 Your superpowers" subtitle="Strengths showing up across your games" list={strengths} />
          <PatternSection title="📈 Your opportunities" subtitle="The leaks costing you the most" list={weaknesses} />
        </div>
      )}
    </div>
  );
}

function PatternSection({
  title,
  subtitle,
  list,
}: {
  title: string;
  subtitle: string;
  list: PlayerPattern[];
}) {
  if (list.length === 0) return null;
  return (
    <section>
      <h2 className="font-display text-xl font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-[#bbcabf]">{subtitle}</p>
      <ul className="mt-4 space-y-3">
        {list.map((pattern) => (
          <li
            key={pattern.id}
            className="rounded-2xl border border-[#262626] bg-[#141414] px-5 py-4"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                  pattern.is_strength
                    ? 'bg-brand-primary/10 text-brand-primary'
                    : 'bg-amber-500/10 text-amber-400'
                }`}
              >
                {pattern.pattern_type}
                {pattern.pattern_subtype ? ` · ${pattern.pattern_subtype}` : ''}
              </span>
              <span className="rounded-full bg-[#242424] px-2 py-0.5 text-[11px] text-[#bbcabf]">
                {pattern.affected_games_count} games
              </span>
              {pattern.trend_direction && (
                <span className="rounded-full bg-[#242424] px-2 py-0.5 text-[11px] text-[#bbcabf]">
                  trending {pattern.trend_direction}
                </span>
              )}
            </div>
            <p className="mt-2 text-[15px] leading-7 text-[#e5e2e1]">{pattern.pattern_description}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
