import { useEffect, useState } from 'react';
import { Loader2, RefreshCw, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import { AppShell } from '@/components/coach/AppShell';
import api from '@/lib/api';
import { useCurrentUser } from '@/hooks';
import type { TrainingDrill } from '@/lib/api';

const EXTERNAL_PARTNERS = [
  {
    name: 'ChessReps',
    description: 'Spaced-repetition repertoire drilling — lock in your openings move by move.',
  },
  {
    name: 'ChessFlow',
    description: 'Guided calculation flow training for your recurring tactical themes.',
  },
];

export default function TrainingPage() {
  return (
    <AppShell>
      <TrainingBody />
    </AppShell>
  );
}

function statHeading(label: string, value: string | number, suffix?: string) {
  return (
    <div>
      <p className="text-[17px] font-semibold text-content">{label}</p>
      <p className="mt-1 flex items-baseline gap-2">
        <span className="text-[40px] font-bold leading-none tracking-tight text-content">
          {value}
        </span>
        {suffix && <span className="text-sm text-content-muted">{suffix}</span>}
      </p>
    </div>
  );
}

function TrainingBody() {
  const { user, loading } = useCurrentUser();
  const [drills, setDrills] = useState<TrainingDrill[]>([]);
  const [drillsLoading, setDrillsLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);

  useEffect(() => {
    if (!user) return;
    let active = true;
    void (async () => {
      try {
        const activePlan = await api.training.getActivePlan(user.id);
        if (active) setDrills(activePlan.drills ?? []);
      } catch {
        // No active plan yet — that's a normal empty state, not an error.
        if (active) setDrills([]);
      } finally {
        if (active) setDrillsLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [user]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface text-content-muted">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Loading drills...
      </div>
    );
  }

  const patternDrills = drills.filter((d) => d.pattern_id != null);
  const insightDrills = drills.filter((d) => d.pattern_id == null);

  return (
    <div className="min-h-screen bg-surface">
      <div className="mx-auto max-w-[1100px] px-5 pb-20 pt-6 sm:px-10">
        <header className="mb-8">
          <p className="text-[15px] font-medium text-content">Drills</p>
        </header>

        {/* Drills card (12902 card anatomy) */}
        <section className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 p-8 sm:px-10 sm:py-10">
          <div className="flex items-start justify-between gap-4">
            {statHeading(
              'Your Training Plan',
              drillsLoading ? '…' : drills.length,
              drills.length === 1 ? 'drill' : 'drills',
            )}
            <button
              type="button"
              disabled={rebuilding}
              onClick={() => {
                toast('Drill plans regenerate after each pattern rebuild', { icon: '💡' });
              }}
              className="mt-1 flex shrink-0 items-center gap-2 rounded-xl bg-surface-low/70 px-4 py-2.5 text-sm font-medium text-content transition-colors hover:bg-surface-bright/40 disabled:opacity-60"
            >
              <RefreshCw className={`h-4 w-4 ${rebuilding ? 'animate-spin' : ''}`} />
              How it works
            </button>
          </div>

          <div className="mt-8">
            {drillsLoading ? (
              <div className="flex items-center justify-center py-12 text-content-muted">
                <Loader2 className="mr-2 h-4 w-4 animate-spin text-brand-primary" /> Loading your
                plan...
              </div>
            ) : drills.length === 0 ? (
              <p className="py-10 text-center text-[15px] text-content-muted">
                No drills yet — they appear after analysis runs and patterns are detected.
              </p>
            ) : (
              <div>
                {patternDrills.length > 0 && <DrillTable title="From your patterns" list={patternDrills} />}
                {insightDrills.length > 0 && (
                  <DrillTable title="From coach insights" list={insightDrills} />
                )}
              </div>
            )}
          </div>
        </section>

        {/* partner cards (12907 reveal style) */}
        <section className="mt-10">
          <h2 className="text-[22px] font-bold tracking-tight text-content">
            Recommended via partners
          </h2>
          <p className="mt-1 text-sm text-content-muted">
            Hand off your weakest areas to dedicated training tools.
          </p>
          <div className="mt-5 grid gap-5 sm:grid-cols-2">
            {EXTERNAL_PARTNERS.map((partner) => (
              <div
                key={partner.name}
                className="flex h-full flex-col items-center rounded-2xl border border-surface-bright/30 bg-surface-container/70 px-8 py-9 text-center"
              >
                <p className="text-[15px] font-semibold text-content-muted">
                  ⚡ {partner.name}
                </p>
                <p className="mx-auto mt-3 max-w-[34ch] text-[19px] font-bold leading-snug tracking-tight text-content">
                  {partner.description}
                </p>
                <span className="mt-5 rounded-full bg-surface-bright/40 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-content-muted">
                  Coming soon
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function DrillTable({ title, list }: { title: string; list: TrainingDrill[] }) {
  return (
    <div className={title.includes('insights') ? 'mt-8' : ''}>
      <p className="mb-3 flex items-center gap-2 text-[13px] text-content-muted">
        <Sparkles className="h-3.5 w-3.5 text-brand-primary" /> {title}
      </p>
      <ul>
        {list.map((drill) => (
          <li
            key={drill.id}
            className="flex items-start justify-between gap-4 border-b border-surface-bright/20 py-4 last:border-b-0"
          >
            <div className="min-w-0">
              <p className="text-[15px] leading-6 text-content">
                {drill.prompt_text.length > 90
                  ? `${drill.prompt_text.slice(0, 90)}…`
                  : drill.prompt_text}
              </p>
              <span className="mt-1.5 inline-block rounded-md bg-brand-primary/10 px-1.5 py-0.5 text-[11px] font-semibold text-brand-primary">
                {drill.drill_type}
              </span>
            </div>
            {drill.status && (
              <span className="shrink-0 rounded-full bg-surface-bright/40 px-2.5 py-0.5 text-[11px] text-content-muted">
                {drill.status}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
