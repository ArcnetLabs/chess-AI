import { useRouter } from 'next/router';
import {
  Brain,
  CheckCircle2,
  Clock,
  CreditCard,
  Loader2,
  Lock,
  Sparkles,
} from 'lucide-react';
import { AppShell } from '@/components/coach/AppShell';
import { useCurrentUser } from '@/hooks';

const PRO_FEATURES = [
  {
    icon: Brain,
    title: 'Full-history analysis',
    body: 'Analyze your entire Chess.com game history — not just the most recent 200 games — so patterns and trends span years, not months.',
  },
  {
    icon: Sparkles,
    title: 'Deeper pattern engine',
    body: 'Every recurring leak, phase weakness, and opening trap escalated to the full pattern library with drill recommendations.',
  },
  {
    icon: Clock,
    title: 'Priority analysis queue',
    body: 'Your fresh games jump the line — analysis completes in minutes even on peak evenings.',
  },
  {
    icon: Lock,
    title: 'Extended coach memory',
    body: 'ChessRun remembers every session across weeks, building a longer, sharper coaching arc.',
  },
];

export default function BillingPage() {
  return (
    <AppShell>
      <BillingBody />
    </AppShell>
  );
}

function BillingBody() {
  const router = useRouter();
  const { user, loading } = useCurrentUser();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface text-content-muted">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Loading billing...
      </div>
    );
  }

  const name = user?.chesscom_username ?? user?.email?.split('@')[0] ?? 'there';

  return (
    <div className="min-h-screen bg-surface">
      <div className="mx-auto max-w-[1100px] px-5 pb-20 pt-6 sm:px-10">
        <header>
          <p className="text-[13px] font-semibold uppercase tracking-wider text-content-muted">
            Billing
          </p>
          <h1 className="mt-1 text-[28px] font-bold tracking-tight text-content">
            Hi {name} — here&apos;s the plan
          </h1>
          <p className="mt-2 max-w-[44rem] text-[15px] leading-7 text-content-muted">
            Everything you&apos;re using today — the coach, insights, patterns, and your recent-200
            game analysis — stays free. Pro unlocks the deep work.
          </p>
        </header>

        {/* coming soon banner — pricing not enforced yet */}
        <div className="mt-7 flex items-center justify-between gap-4 rounded-2xl border border-brand-primary/25 bg-brand-primary/[0.05] px-7 py-5">
          <div className="flex items-center gap-3">
            <CreditCard className="h-5 w-5 shrink-0 text-brand-primary" />
            <div>
              <p className="text-[16px] font-bold text-content">ChessRun Pro is coming soon</p>
              <p className="mt-0.5 text-sm text-content-muted">
                Purchase isn&apos;t available yet — nothing to pay today.
              </p>
            </div>
          </div>
          <span className="hidden shrink-0 rounded-full border border-brand-primary/30 px-4 py-1.5 text-[13px] font-semibold text-brand-primary sm:block">
            Coming soon
          </span>
        </div>

        {/* free vs pro cards — no prices, by design */}
        <div className="mt-7 grid gap-5 sm:grid-cols-2">
          {/* Free */}
          <section className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 p-8">
            <div className="flex items-center justify-between">
              <h2 className="text-[19px] font-bold text-content">Free</h2>
              <span className="rounded-full bg-surface-bright/40 px-3 py-1 text-[12px] font-semibold text-content-muted">
                Your plan · Forever
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-content-muted">
              What you&apos;re using right now, no card needed.
            </p>
            <ul className="mt-6 space-y-3.5">
              {[
                'Unlimited coach chats grounded in your games',
                'Insights, patterns & drills pages',
                'Engine analysis of your most recent 200 games',
                'Game-by-game chat on any analyzed game',
              ].map((item) => (
                <li key={item} className="flex items-start gap-2.5">
                  <CheckCircle2 className="mt-0.5 h-4.5 w-4.5 shrink-0 text-brand-primary" />
                  <span className="text-[14.5px] leading-6 text-content">{item}</span>
                </li>
              ))}
            </ul>
          </section>

          {/* Pro */}
          <section className="relative rounded-2xl border border-brand-primary/30 bg-brand-primary/[0.04] p-8">
            <div className="absolute -top-3 right-6 rounded-full bg-brand-primary px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-brand-on-primary">
              Pro · Coming soon
            </div>
            <div className="flex items-center justify-between">
              <h2 className="text-[19px] font-bold text-content">Pro</h2>
              <span className="rounded-full border border-brand-primary/30 px-3 py-1 text-[12px] font-semibold text-brand-primary">
                TBD · Announced at launch
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-content-muted">
              Built for players who want the full picture of their chess.
            </p>
            <ul className="mt-6 space-y-3.5">
              {[
                'Full-history analysis — every game you ever played',
                'Deeper pattern engine with drill recommendations',
                'Priority analysis queue',
                'Extended coach memory across weeks',
              ].map((item) => (
                <li key={item} className="flex items-start gap-2.5">
                  <CheckCircle2 className="mt-0.5 h-4.5 w-4.5 shrink-0 text-brand-primary" />
                  <span className="text-[14.5px] leading-6 text-content">{item}</span>
                </li>
              ))}
            </ul>
            <button
              type="button"
              disabled
              className="mt-7 w-full cursor-not-allowed rounded-full border border-brand-primary/30 bg-transparent px-6 py-3.5 text-[15px] font-semibold text-brand-primary opacity-70"
            >
              Paid plans announced at launch
            </button>
            <p className="mt-3 text-center text-xs text-content-muted/70">
              You&apos;ll be the first to know — we&apos;ll notify you in-app.
            </p>
          </section>
        </div>

        {/* pro feature detail */}
        <section className="mt-10">
          <h2 className="text-[17px] font-semibold text-content">
            What Pro unlocks
          </h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {PRO_FEATURES.map(({ icon: Icon, title, body }) => (
              <div
                key={title}
                className="flex gap-3.5 rounded-2xl border border-surface-bright/30 bg-surface-container/70 px-6 py-5"
              >
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-primary/12">
                  <Icon className="h-4.5 w-4.5 text-brand-primary" />
                </span>
                <div>
                  <p className="text-[15px] font-bold text-content">{title}</p>
                  <p className="mt-1 text-[13.5px] leading-6 text-content-muted">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <button
          type="button"
          onClick={() => void router.push('/coach')}
          className="mt-10 w-full rounded-full bg-brand-primary px-6 py-4 text-[16px] font-semibold text-brand-on-primary shadow-brand-glow transition-opacity hover:opacity-90"
        >
          Back to ChessRun
        </button>
      </div>
    </div>
  );
}
