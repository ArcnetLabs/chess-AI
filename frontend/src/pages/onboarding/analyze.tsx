import { useRouter } from 'next/router';
import { useEffect, useMemo, useState } from 'react';
import { Loader2, Sparkles, TrendingUp } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '@/lib/api';
import { KnightGlyph } from '@/components/brand/ChessRunMark';
import { useAnalysisStatus, useCurrentUser, usePlayerProfile } from '@/hooks';

type Phase =
  | 'ready'
  | 'analyzing'
  | 'done'
  | 'error'
  | 'building';

const STAGES = [
  'Fetching your games',
  'Running engine analysis',
  'Detecting patterns',
  'Building your profile',
];

export default function AnalyzeOnboardingPage() {
  return <AnalyzeOnboardingBody />;
}

function AnalyzeOnboardingBody() {
  const router = useRouter();
  const { user, loading } = useCurrentUser();
  const { data: profile, refetch: refetchProfile } = usePlayerProfile(user?.id);
  const { watchJob, error: jobError } = useAnalysisStatus(user?.id);
  const [phase, setPhase] = useState<'ready' | 'analyzing' | 'done' | 'error'>('ready');
  const [stageIndex, setStageIndex] = useState(0);
  const [progress, setProgress] = useState(6);

  useEffect(() => {
    if (phase !== 'analyzing') return;
    const timer = window.setInterval(() => {
      setProgress((current) => {
        const next = current + (98 - current) * 0.06;
        return Math.min(next, 97);
      });
      setStageIndex((current) => Math.min(current + (Math.random() > 0.6 ? 1 : 0), STAGES.length - 1));
    }, 700);
    return () => window.clearInterval(timer);
  }, [phase]);

  const startAnalysis = async () => {
    if (!user) return;
    setPhase('analyzing');
    setProgress(6);
    setStageIndex(0);
    try {
      await api.games.fetchRecent(user.id, { days: undefined });
      const response = await api.analysis.analyzeGames(user.id, { days: undefined });
      if (
        response &&
        typeof response === 'object' &&
        'status' in response &&
        (response as { status?: string }).status === 'queued' &&
        (response as { job_id?: string }).job_id
      ) {
        watchJob((response as { job_id: string }).job_id, {
          onComplete: async () => {
            setProgress(100);
            setStageIndex(STAGES.length - 1);
            void refetchProfile();
            setPhase('done');
            toast.success('Your games are analyzed');
          },
          onError: () => setPhase('error'),
        });
      } else {
        setPhase('done');
      }
    } catch {
      setPhase('error');
    }
  };

  if (loading) {
    return (
      <Page>
        <div className="flex items-center justify-center text-content-muted">
          <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Preparing your
          analysis...
        </div>
      </Page>
    );
  }

  if (phase === 'analyzing') {
    return (
      <Page>
        <div className="space-y-8 text-center">
          <KnightGlyph className="mx-auto h-12 w-12 animate-pulse text-brand-primary" />
          <h1 className="text-2xl font-bold tracking-tight text-content">{STAGES[stageIndex]}...</h1>
          <div className="h-2 w-full overflow-hidden rounded-full bg-surface-low">
            <div
              className="h-full rounded-full bg-brand-primary transition-[width] duration-700 ease-out"
              style={{ width: `${Math.round(progress)}%` }}
            />
          </div>
          <p className="text-sm text-content-muted">
            Analyzing every game so your coach sees your real tendencies — this takes a minute or
            two.
          </p>
        </div>
      </Page>
    );
  }

  if (phase === 'error') {
    return (
      <Page>
        <div className="space-y-6 text-center">
          <h1 className="text-2xl font-bold tracking-tight text-content">Something went wrong</h1>
          <p className="text-sm text-content-muted">
            {typeof jobError === 'string'
              ? jobError
              : jobError instanceof Error
                ? jobError.message
                : 'We could not finish the analysis. Please try again.'}
          </p>
          <button
            type="button"
            onClick={() => void startAnalysis()}
            className="w-full rounded-chess-lg bg-brand-primary px-6 py-4 text-[17px] font-semibold text-brand-on-primary transition-opacity hover:opacity-90"
          >
            Retry analysis
          </button>
        </div>
      </Page>
    );
  }

  if (phase === 'done') {
    return (
      <Page>
        <div className="space-y-10">
          {/* centered avatar + one-line identity (12907) */}
          <div className="space-y-6 text-center">
            <div className="mx-auto h-20 w-20 overflow-hidden rounded-full border border-surface-bright/40 shadow-brand-ambient">
              {user?.chesscom_avatar ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={user.chesscom_avatar}
                  alt="Your avatar"
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center bg-surface-container">
                  <KnightGlyph className="h-10 w-10 text-brand-primary" />
                </div>
              )}
            </div>
            <h1 className="mx-auto max-w-[42rem] text-[24px] font-bold leading-relaxed tracking-tight text-content sm:text-[27px]">
              {profile?.profile_summary
                ? profile.profile_summary
                : 'Every game analyzed — your coach now sees how you actually play.'}
            </h1>
          </div>

          {/* stat grid (12907) */}
          <div className="grid gap-5 sm:grid-cols-2">
            <div className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 p-7">
              <p className="text-[15px] text-content-muted">Games analyzed</p>
              <p className="mt-1 text-[40px] font-bold leading-none tracking-tight text-content">
                {profile?.games_analyzed_count ?? 0}
              </p>
              {profile?.archetype && (
                <div className="mt-6">
                  <div className="flex justify-between text-[11px] font-semibold text-content-muted">
                    <span>SOLID</span>
                    <span>AVG</span>
                    <span>SHARP</span>
                  </div>
                  <div className="relative mt-2 h-1.5 rounded-full bg-surface-bright/40">
                    <div className="absolute left-1/2 top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface bg-brand-primary" />
                  </div>
                  <p className="mt-3 text-center text-[15px] font-bold text-content">
                    {profile.archetype}
                  </p>
                </div>
              )}
            </div>
            <div className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 p-7">
              <div className="flex items-center justify-between">
                <p className="text-[15px] text-content-muted">Projected rating growth</p>
                <TrendingUp className="h-4.5 w-4.5 text-brand-primary" />
              </div>
              <GrowthSketch />
              <div className="mt-2 flex justify-between text-xs text-content-muted">
                <span>Today</span>
                <span>+90 days</span>
              </div>
            </div>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div className="rounded-2xl border border-brand-primary/20 bg-brand-primary/[0.04] px-8 py-9 text-center">
              <p className="text-[15px] font-semibold text-content-muted">🔥 Your Superpower</p>
              <p className="mx-auto mt-3 max-w-[30ch] text-[24px] font-bold leading-snug tracking-tight text-content">
                Your consistent score in winning positions
              </p>
            </div>
            <div className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 px-8 py-9 text-center">
              <p className="text-[15px] font-semibold text-content-muted">📈 Your Opportunity</p>
              <p className="mx-auto mt-3 max-w-[30ch] text-[24px] font-bold leading-snug tracking-tight text-content">
                {profile?.primary_weaknesses?.length
                  ? 'Your most frequent game-phase leak'
                  : 'Convert more of your equal positions'}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => void router.push('/coach')}
            className="w-full rounded-full bg-brand-primary px-6 py-4 text-[17px] font-semibold text-brand-on-primary shadow-brand-glow transition-opacity hover:opacity-90"
          >
            Chat with ChessRun
          </button>
        </div>
      </Page>
    );
  }

  return (
    <Page>
      <div className="space-y-2 text-center">
        <KnightGlyph className="mx-auto mb-6 h-16 w-16 text-brand-primary" />
        <h1 className="mx-auto max-w-[40rem] text-[26px] font-bold leading-relaxed tracking-tight text-content sm:text-[28px]">
          Let&apos;s analyze your games
        </h1>
        <p className="mx-auto max-w-[34rem] text-[15px] leading-7 text-content-muted">
          We&apos;ll pull your full game history from Chess.com and run analysis on all of it —
          that&apos;s how your coach builds a profile of how you actually play, not guesswork.
        </p>
      </div>
      <div className="mt-9">
        <button
          type="button"
          onClick={() => void startAnalysis()}
          className="mx-auto flex w-full items-center justify-center gap-2 rounded-full bg-brand-primary px-6 py-4 text-[17px] font-semibold text-brand-on-primary shadow-brand-glow transition-opacity hover:opacity-90"
        >
          <Sparkles className="h-5 w-5" /> Analyze my games
        </button>
        <p className="mt-4 text-center text-xs text-content-muted/60">
          Full history · Engine eval on every move · Takes 1–2 minutes
        </p>
      </div>
    </Page>
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

function Page({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-6 py-16">
      <div className="w-full max-w-[760px]">{children}</div>
    </div>
  );
}
