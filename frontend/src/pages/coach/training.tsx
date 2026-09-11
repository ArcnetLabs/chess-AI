import { useEffect, useState } from 'react';
import { Dumbbell, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { AppShell } from '@/components/coach/AppShell';
import api from '@/lib/api';
import { useCurrentUser } from '@/hooks';
import type { TrainingDrill } from '@/lib/api';

const EXTERNAL_PARTNERS = [
  {
    name: 'ChessReps',
    description: 'Spaced-repetition repetoire drilling — lock in your openings move by move.',
    enabled: false,
  },
  {
    name: 'ChessFlow',
    description: 'Guided calculation flow training for your recurring tactical themes.',
    enabled: false,
  },
];

export default function TrainingPage() {
  return (
    <AppShell>
      <TrainingBody />
    </AppShell>
  );
}

function TrainingBody() {
  const { user, loading } = useCurrentUser();
  const [drills, setDrills] = useState<TrainingDrill[]>([]);
  const [drillsLoading, setDrillsLoading] = useState(true);

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
      <div className="flex min-h-screen items-center justify-center text-[#bbcabf]">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Loading drills...
      </div>
    );
  }

  const patternDrills = drills.filter((d) => d.pattern_id != null);
  const insightDrills = drills.filter((d) => d.pattern_id == null);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-8">
      <header>
        <p className="flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-brand-primary">
          <Dumbbell className="h-4 w-4" /> Drills
        </p>
        <h1 className="mt-1 font-display text-3xl font-bold tracking-tight">Your training plan</h1>
        <p className="mt-2 text-sm text-[#bbcabf]">
          Drill recommendations generated from your patterns and coach insights, refreshed as your
          play evolves.
        </p>
      </header>

      {drillsLoading ? (
        <div className="mt-10 flex items-center justify-center py-10 text-[#bbcabf]">
          <Loader2 className="mr-2 h-4 w-4 animate-spin text-brand-primary" /> Loading your plan...
        </div>
      ) : drills.length === 0 ? (
        <p className="mt-10 rounded-2xl border border-[#262626] bg-[#141414] px-6 py-10 text-center text-sm text-[#bbcabf]">
          No drills yet — they appear after analysis runs and patterns are detected.
        </p>
      ) : (
        <div className="mt-8 space-y-10">
          {patternDrills.length > 0 && (
            <DrillSection title="From your patterns" list={patternDrills} />
          )}
          {insightDrills.length > 0 && (
            <DrillSection title="From coach insights" list={insightDrills} />
          )}
        </div>
      )}

      <section className="mt-12">
        <h2 className="font-display text-xl font-semibold">Recommended via partners</h2>
        <p className="mt-1 text-sm text-[#bbcabf]">
          Handoff your weakest areas to dedicated training tools. Integration coming soon.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {EXTERNAL_PARTNERS.map((partner) => (
            <div
              key={partner.name}
              className="rounded-2xl border border-[#262626] bg-[#141414] p-5 opacity-80"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-medium text-[#e5e2e1]">{partner.name}</h3>
                <span className="rounded-full bg-[#242424] px-2.5 py-0.5 text-[11px] uppercase tracking-wider text-[#bbcabf]">
                  Coming soon
                </span>
              </div>
              <p className="mt-2 text-sm leading-6 text-[#bbcabf]">{partner.description}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function DrillSection({ title, list }: { title: string; list: TrainingDrill[] }) {
  return (
    <section>
      <h2 className="font-display text-xl font-semibold">{title}</h2>
      <ul className="mt-4 space-y-3">
        {list.map((drill) => (
          <li
            key={drill.id}
            className="flex items-start justify-between gap-4 rounded-2xl border border-[#262626] bg-[#141414] px-5 py-4"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-[15px] font-medium text-[#e5e2e1]">{drill.prompt_text.length > 80 ? `${drill.prompt_text.slice(0, 80)}...` : drill.prompt_text}</h3>
                <span className="rounded-full bg-brand-primary/10 px-2.5 py-0.5 text-[11px] font-medium text-brand-primary">
                  {drill.drill_type}
                </span>
              </div>
              
            </div>
            {drill.status && (
              <span className="shrink-0 rounded-full bg-[#242424] px-2.5 py-0.5 text-[11px] text-[#bbcabf]">
                {drill.status}
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
