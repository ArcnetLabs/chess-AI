import { useEffect, useState } from 'react';
import { ArrowUpRight, Loader2, Target } from 'lucide-react';
import { AppShell } from '@/components/coach/AppShell';
import api from '@/lib/api';
import type { PracticeFocus, PracticeFocusItem } from '@/lib/api';
import { useCurrentUser } from '@/hooks';

/**
 * What to work on, and where to do the work.
 *
 * ChessRun is the coach, not the training ground: players do their reps on
 * ChessReps and ChessFlow. So this page prescribes — the situation you keep
 * getting wrong, the evidence behind it, and the platform that fits — and does
 * not pretend to host practice or to know what exists on a partner we are not
 * integrated with yet.
 */
export default function PracticePage() {
  return (
    <AppShell>
      <PracticeBody />
    </AppShell>
  );
}

function trendLabel(trend: string | null): string | null {
  if (!trend) return null;
  if (trend === 'persistent') return 'Keeps happening';
  if (trend === 'worsening') return 'Getting worse';
  if (trend === 'improving') return 'Improving';
  if (trend === 'resolved') return 'Not seen lately';
  if (trend === 'new') return 'New';
  return null;
}

function PracticeBody() {
  const { user, loading } = useCurrentUser();
  const [focus, setFocus] = useState<PracticeFocus | null>(null);
  const [focusLoading, setFocusLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    let active = true;
    void (async () => {
      try {
        const data = await api.practice.getFocus(user.id);
        if (active) setFocus(data);
      } catch {
        // No focus yet is a normal state, not an error.
        if (active) setFocus({ focus: [], partners: [] });
      } finally {
        if (active) setFocusLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [user]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface text-content-muted">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Loading your focus...
      </div>
    );
  }

  const items = focus?.focus ?? [];
  const partners = focus?.partners ?? [];

  return (
    <div className="min-h-screen bg-surface">
      <div className="mx-auto max-w-[1100px] px-5 pb-20 pt-6 sm:px-10">
        <header className="mb-8">
          <p className="text-[15px] font-medium text-content">Practice focus</p>
          <p className="mt-2 max-w-[62ch] text-sm leading-6 text-content-muted">
            What your games say is worth working on next, and where to do the work. Your coach
            reads the same list, so asking about any of it picks up exactly here.
          </p>
        </header>

        <section className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 p-8 sm:px-10 sm:py-10">
          <h1 className="text-[22px] font-bold tracking-tight text-content">Work on this next</h1>

          <div className="mt-6">
            {focusLoading ? (
              <div className="flex items-center justify-center py-12 text-content-muted">
                <Loader2 className="mr-2 h-4 w-4 animate-spin text-brand-primary" /> Reading your
                patterns...
              </div>
            ) : items.length === 0 ? (
              <p className="py-10 text-center text-[15px] leading-6 text-content-muted">
                Nothing to work on yet. Analyze a batch of your games and your focus will appear
                here, built from what actually keeps happening in them.
              </p>
            ) : (
              <ul className="space-y-5">
                {items.map((item) => (
                  <FocusRow key={item.pattern_id} item={item} />
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="mt-10">
          <h2 className="text-[22px] font-bold tracking-tight text-content">Where to practise</h2>
          <p className="mt-1 max-w-[62ch] text-sm leading-6 text-content-muted">
            Your reps live on our partner platforms. ChessRun keeps the coaching conversation;
            these are where the work happens.
          </p>
          <div className="mt-5 grid gap-5 sm:grid-cols-2">
            {partners.map((partner) => (
              <div
                key={partner.key}
                className="flex h-full flex-col rounded-2xl border border-surface-bright/30 bg-surface-container/70 px-8 py-9"
              >
                <p className="text-[15px] font-semibold text-content">{partner.name}</p>
                <p className="mt-2 text-sm leading-6 text-content-muted">{partner.focus}</p>
                <span className="mt-5 inline-flex w-fit rounded-full bg-surface-bright/40 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-content-muted">
                  {partner.url ? 'Open' : 'Connecting soon'}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function FocusRow({ item }: { item: PracticeFocusItem }) {
  const trend = trendLabel(item.trend);
  return (
    <li className="rounded-xl border border-surface-bright/25 bg-surface-low/40 px-5 py-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p className="flex items-center gap-2 text-[17px] font-semibold text-content">
          <Target className="h-4 w-4 shrink-0 text-brand-primary" />
          {item.focus}
        </p>
        {trend && <span className="text-[12px] text-content-muted">{trend}</span>}
      </div>
      <p className="mt-2 text-sm leading-6 text-content-muted">
        {item.why}
        {item.situations > 1
          ? ` You meet it in ${item.situations} different kinds of position.`
          : ''}
      </p>
      <p className="mt-3 flex items-center gap-1.5 text-[13px] text-content-muted">
        {item.partner ? (
          <>
            <ArrowUpRight className="h-3.5 w-3.5 text-brand-primary" />
            Practise this on {item.partner.name} — {item.partner.focus}
          </>
        ) : (
          <>Bring this into your next session with your coach</>
        )}
      </p>
    </li>
  );
}
