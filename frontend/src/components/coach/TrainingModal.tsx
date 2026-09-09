import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, Loader2, Target, X } from 'lucide-react';
import toast from 'react-hot-toast';
import {
  trainingApi,
  type TrainingDrill,
  type TrainingPlanDetail,
  type TrainingProgress,
} from '@/lib/api';

const DRILL_TYPE_LABELS: Record<string, string> = {
  tactic: 'Tactics',
  endgame: 'Endgame',
  opening: 'Opening',
  conversion: 'Conversion',
  pattern_recognition: 'Pattern Recognition',
  calculation: 'Calculation',
};

function drillTypeLabel(value: string): string {
  return DRILL_TYPE_LABELS[value.toLowerCase()] ?? value.replace(/_/g, ' ');
}

export function TrainingModal({
  userId,
  onClose,
}: {
  userId: number;
  onClose: () => void;
}) {
  const [plan, setPlan] = useState<TrainingPlanDetail | null>(null);
  const [progress, setProgress] = useState<TrainingProgress | null>(null);
  const [planMissing, setPlanMissing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyDrillId, setBusyDrillId] = useState<number | null>(null);
  const [answerDrafts, setAnswerDrafts] = useState<Record<number, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setPlanMissing(false);
    try {
      const progressResponse = await trainingApi.getProgress(userId);
      setProgress(progressResponse);
      try {
        const planResponse = await trainingApi.getActivePlan(userId);
        setPlan(planResponse);
      } catch {
        setPlan(null);
        setPlanMissing(true);
      }
    } catch {
      setError('Could not load your training plan. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void load();
  }, [load]);

  const refreshAfterAction = (updatedDrill: TrainingDrill) => {
    if (!plan) return;
    const drills = plan.drills.map((drill) =>
      drill.id === updatedDrill.id ? updatedDrill : drill,
    );
    const completed = drills.filter((drill) => drill.status === 'completed').length;
    setPlan({ ...plan, drills, completed_drill_count: completed });
  };

  const handleStart = async (drill: TrainingDrill) => {
    setBusyDrillId(drill.id);
    try {
      const updated = await trainingApi.setDrillStatus(userId, drill.id, 'in_progress');
      if (updated) refreshAfterAction(updated);
    } catch {
      toast.error('Could not start the drill. Please try again.');
    } finally {
      setBusyDrillId(null);
    }
  };

  const handleComplete = async (drill: TrainingDrill, isCorrect: boolean) => {
    setBusyDrillId(drill.id);
    const userAnswer = (answerDrafts[drill.id] ?? '').trim();
    try {
      const updated = await trainingApi.completeDrill(userId, drill.id, {
        user_answer: userAnswer || '(no answer recorded)',
        is_correct: isCorrect,
      });
      if (updated) refreshAfterAction(updated);
      if (isCorrect) toast.success('Drill marked as solved. Keep the streak going.');
      else toast('Marked as missed — review it again soon.');
      void load();
    } catch {
      toast.error('Could not record the drill result. Please try again.');
    } finally {
      setBusyDrillId(null);
    }
  };

  const handleSkip = async (drill: TrainingDrill) => {
    setBusyDrillId(drill.id);
    try {
      const updated = await trainingApi.setDrillStatus(userId, drill.id, 'skipped');
      if (updated) refreshAfterAction(updated);
    } catch {
      toast.error('Could not skip the drill. Please try again.');
    } finally {
      setBusyDrillId(null);
    }
  };

  const planProgress = plan && plan.drill_count > 0 ? Math.round((plan.completed_drill_count / plan.drill_count) * 100) : 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end bg-black/70 p-0 backdrop-blur-sm sm:items-center sm:justify-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Your training plan"
    >
      <div className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-t-2xl border border-[#3c4a42] bg-[#201f1f] p-6 shadow-2xl sm:rounded-xl">
        <div className="mb-6 flex items-start justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-wider text-brand-primary">
              Training
            </p>
            <h2 className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <Target className="h-6 w-6 text-brand-primary" /> Your Training Plan
            </h2>
            <p className="mt-2 text-sm leading-6 text-[#bbcabf]">
              Drills your coach authors from your patterns and interview goals. Work through them
              at the board — every completed drill sharpens your focus areas.
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
              training plan...
            </div>
          ) : error ? (
            <p className="py-6 text-center text-sm text-brand-error">{error}</p>
          ) : planMissing || !plan ? (
            <p className="py-10 text-center text-sm leading-6 text-[#bbcabf]">
              No training plan yet. Start an interview or ask your coach for drills tailored to
              your pattern profile — everything your coach saves shows up here.
            </p>
          ) : (
            <>
              <div className="rounded-lg border border-[#3c4a42] bg-[#171717] p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-mono text-sm font-semibold text-[#e5e2e1]">{plan.title}</p>
                  <p className="font-mono text-xs text-[#bbcabf]">
                    Plan #{plan.plan_version} · {plan.completed_drill_count}/{plan.drill_count} done
                  </p>
                </div>
                {plan.focus_areas && plan.focus_areas.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {plan.focus_areas.map((area) => (
                      <span
                        key={area}
                        className="rounded-full border border-[#3c4a42] px-3 py-1 text-xs text-[#bbcabf]"
                      >
                        {area}
                      </span>
                    ))}
                  </div>
                )}
                <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-black/30">
                  <div
                    className="h-full rounded-full bg-brand-primary transition-all"
                    style={{ width: `${Math.max(3, planProgress)}%` }}
                  />
                </div>
              </div>

              <ul className="mt-4 space-y-3">
                {plan.drills.map((drill) => {
                  const isDone = drill.status === 'completed';
                  const isSkipped = drill.status === 'skipped';
                  const isInProgress = drill.status === 'in_progress';
                  const busy = busyDrillId === drill.id;
                  return (
                    <li
                      key={drill.id}
                      className={`rounded-lg border px-4 py-3 ${
                        isDone
                          ? 'border-brand-primary/40 bg-[#10b981]/10'
                          : isSkipped
                            ? 'border-[#262626] bg-[#171717] opacity-70'
                            : 'border-[#262626] bg-[#171717]'
                      }`}
                    >
                      <p className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wide text-[#bbcabf]">
                        <span className={isSkipped ? '' : 'text-brand-primary'}>
                          {drillTypeLabel(drill.drill_type)}
                        </span>
                        <span className="ml-auto normal-case tracking-normal">
                          {isDone ? (
                            <span className="flex items-center gap-1 text-[#6ffbbe]">
                              <CheckCircle2 className="h-3.5 w-3.5" />
                              {drill.is_correct === false ? 'Marked missed' : 'Solved'}
                            </span>
                          ) : (
                            isSkipped && 'Skipped'
                          )}
                        </span>
                      </p>
                      <p className="mt-1.5 text-sm leading-6 text-[#e5e2e1]">{drill.prompt_text}</p>
                      {isInProgress && (
                        <input
                          value={answerDrafts[drill.id] ?? ''}
                          onChange={(event) =>
                            setAnswerDrafts((drafts) => ({ ...drafts, [drill.id]: event.target.value }))
                          }
                          placeholder="Your answer (optional)..."
                          className="mt-3 w-full rounded-md border border-[#3c4a42] bg-[#131313] px-3 py-2 text-sm text-[#e5e2e1] outline-none focus:border-brand-primary"
                        />
                      )}
                      {!isDone && !isSkipped && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {!isInProgress && (
                            <button
                              type="button"
                              onClick={() => void handleStart(drill)}
                              disabled={busy}
                              className="rounded-md border border-brand-primary px-3 py-1.5 font-mono text-xs text-brand-primary transition-colors hover:bg-brand-primary/10 disabled:opacity-50"
                            >
                              Start drill
                            </button>
                          )}
                          {isInProgress && (
                            <>
                              <button
                                type="button"
                                onClick={() => void handleComplete(drill, true)}
                                disabled={busy}
                                className="rounded-md bg-[#10b981] px-3 py-1.5 font-mono text-xs font-semibold text-[#00422b] disabled:opacity-50"
                              >
                                {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Solved'}
                              </button>
                              <button
                                type="button"
                                onClick={() => void handleComplete(drill, false)}
                                disabled={busy}
                                className="rounded-md border border-[#fc7c78]/60 px-3 py-1.5 font-mono text-xs text-[#ffb4ab] disabled:opacity-50"
                              >
                                Missed it
                              </button>
                            </>
                          )}
                          <button
                            type="button"
                            onClick={() => void handleSkip(drill)}
                            disabled={busy}
                            className="rounded-md px-3 py-1.5 font-mono text-xs text-[#bbcabf] hover:text-[#e5e2e1] disabled:opacity-50"
                          >
                            Skip
                          </button>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>

              {progress && progress.total_drills > plan.drill_count && (
                <p className="mt-4 text-center font-mono text-xs text-[#bbcabf]">
                  All-time: {progress.completed_drills} of {progress.total_drills} drills
                  completed ({progress.completion_rate}%).
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
