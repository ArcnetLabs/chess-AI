import { useRouter } from 'next/router';
import { useEffect, useMemo, useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '@/lib/api';
import { KnightGlyph } from '@/components/brand/ChessRunMark';
import { useAnalysisStatus, useCurrentUser, usePlayerProfile } from '@/hooks';

type Phase = 'ready' | 'analyzing' | 'done' | 'error';

export default function AnalyzeOnboardingPage() {
  return <AnalyzeOnboardingBody />;
}

function AnalyzeOnboardingBody() {
  const router = useRouter();
  const { user, loading } = useCurrentUser();
  const { data: profile, refetch: refetchProfile } = usePlayerProfile(user?.id);
  const { watchJob, error: jobError } = useAnalysisStatus(user?.id);
  const [phase, setPhase] = useState<Phase>('ready');
  const [stageIndex, setStageIndex] = useState(0);
  const [progress, setProgress] = useState(6);

  const STAGES = useMemo(
    () => ['Fetching your games', 'Running engine analysis', 'Detecting patterns', 'Building your profile'],
    [],
  );

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
  }, [phase, STAGES.length]);

  const startAnalysis = async () => {
    if (!user) return;
    setPhase('analyzing');
    setProgress(6);
    setStageIndex(0);
    try {
      await api.games.fetchRecent(user.id, { days: undefined });
      const response = await api.analysis.analyzeGames(user.id, { days: undefined });
      if (response.status === 'queued' && response.job_id) {
        watchJob(response.job_id, {
          onComplete: async () => {
            setProgress(100);
            setStageIndex(STAGES.length - 1);
            setPhase('done');
            void refetchProfile();
            toast.success('Your games are analyzed');
          },
          onError: () => {
            setPhase('error');
          },
        });
      } else {
        setProgress(100);
        setPhase('done');
      }
    } catch {
      setPhase('error');
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0d0d0d] text-[#bbcabf]">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Preparing your
        analysis...
      </div>
    );
  }

  if (phase === 'done') {
    return (
      <Shell>
        <div className="space-y-6">
          <h1 className="font-display text-3xl font-bold">Your profile is ready ðŸŽ‰</h1>
          <p className="text-base leading-7 text-[#bbcabf]">
            {profile?.profile_summary ??
              'Every game has been analyzed. Your coach is ready with grounded facts.'}
          </p>
          <button
            type="button"
            onClick={() => void router.push('/coach')}
            className="w-full rounded-xl bg-brand-primary px-6 py-3.5 text-base font-semibold text-[#0b351f] transition-opacity hover:opacity-90"
          >
            Chat with your coach â†’
          </button>
        </div>
      </Shell>
    );
  }

  if (phase === 'error') {
    return (
      <Shell>
        <div className="space-y-6 text-center">
          <h1 className="font-display text-2xl font-bold">Something went wrong</h1>
          <p className="text-sm text-[#bbcabf]">
            {typeof jobError === 'string' ? jobError : jobError instanceof Error ? jobError.message : 'We could not finish the analysis. Please try again.'}
          </p>
          <button
            type="button"
            onClick={() => void startAnalysis()}
            className="w-full rounded-xl bg-brand-primary px-6 py-3.5 font-semibold text-[#0b351f]"
          >
            Retry analysis
          </button>
        </div>
      </Shell>
    );
  }

  if (phase === 'analyzing') {
    return (
      <Shell>
        <div className="space-y-8 text-center">
          <KnightGlyph className="mx-auto h-12 w-12 animate-pulse text-brand-primary" />
          <h1 className="font-display text-2xl font-bold">
            {STAGES[stageIndex]}...
          </h1>
          <div className="h-2 w-full overflow-hidden rounded-full bg-[#1c1c1c]">
            <div
              className="h-full rounded-full bg-gradient-to-r from-brand-primary to-[#34d399] transition-[width] duration-700 ease-out"
              style={{ width: `${Math.round(progress)}%` }}
            />
          </div>
          <p className="text-xs text-[#bbcabf]">
            Analyzing every game so your coach sees your real tendencies â€” this takes a minute or
            two.
          </p>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="text-center">
        <KnightGlyph className="mx-auto mb-5 h-14 w-14 text-brand-primary" />
        <h1 className="font-display text-3xl font-bold tracking-tight">
          Let&apos;s analyze your games
        </h1>
        <p className="mx-auto mt-3 max-w-md text-sm leading-7 text-[#bbcabf]">
          We&apos;ll pull your full game history from Chess.com and run analysis on all of it â€”
          that&apos;s how your coach builds a profile of how you actually play, not guesswork.
        </p>
      </div>
      <button
        type="button"
        onClick={() => void startAnalysis()}
        className="mt-8 flex w-full items-center justify-center gap-2 rounded-xl bg-brand-primary px-6 py-3.5 text-base font-semibold text-[#0b351f] transition-opacity hover:opacity-90"
      >
        <Sparkles className="h-5 w-5" /> Analyze my games
      </button>
      <p className="mt-3 text-center text-xs text-[#bbcabf]/60">
        Full history Â· Engine eval on every move Â· Takes 1â€“2 minutes
      </p>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0d0d0d] px-6 text-[#e5e2e1]">
      <div className="w-full max-w-md">{children}</div>
    </div>
  );
}
