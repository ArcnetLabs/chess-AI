import { useCallback, useEffect, useRef, useState } from 'react';
import api from '@/lib/api';
import type { AnalysisJobStatus } from '@/types/analysis.types';

const POLL_INTERVAL_MS = 2_500;
// Transient failures (deploy bounce, proxy blip, cold cache) must not kill a
// legitimately long-running job — tolerate a run of misses before surfacing.
const MAX_CONSECUTIVE_FAILURES = 6;
const MAX_404_BUDGET = 10; // job-store lag right after queuing: ~10 misses
const MAX_BACKOFF_MS = 10_000;

export interface WatchAnalysisJobOptions {
  onProgress?: (status: AnalysisJobStatus) => void;
  onComplete?: (status: AnalysisJobStatus) => void;
  onError?: (error: Error) => void;
  onTimeout?: (status: AnalysisJobStatus) => void;
}

function isTerminal(status: AnalysisJobStatus['status']): boolean {
  return status === 'completed' || status === 'partial' || status === 'failed' || status === 'cancelled';
}

/**
 * Tracks analysis through the job-status endpoint instead of relying only on
 * a long-lived SSE connection. Render proxies can end an SSE response while
 * the Celery job keeps running; polling preserves the actual job state.
 */
export function useAnalysisStatus(userId: number | undefined) {
  const [status, setStatus] = useState<AnalysisJobStatus | null>(null);
  const [isTracking, setIsTracking] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);

  const stop = useCallback(() => {
    cancelledRef.current = true;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setIsTracking(false);
  }, []);

  useEffect(() => stop, [stop]);

  const watchJob = useCallback(
    (jobId?: string, options?: WatchAnalysisJobOptions) => {
      if (!userId || !jobId) {
        const nextError = new Error('Analysis did not return a job identifier.');
        setError(nextError);
        options?.onError?.(nextError);
        return;
      }

      stop();
      cancelledRef.current = false;
      setError(null);
      setIsTracking(true);

      const poll = async (consecutiveFailures = 0) => {
        try {
          const nextStatus = await api.analysis.getJobStatus(userId, jobId);
          if (cancelledRef.current) return;

          setStatus(nextStatus);
          options?.onProgress?.(nextStatus);

          if (!isTerminal(nextStatus.status)) {
            timerRef.current = setTimeout(() => void poll(0), POLL_INTERVAL_MS);
            return;
          }

          setIsTracking(false);
          timerRef.current = null;

          if (nextStatus.status === 'failed') {
            const detail = nextStatus.last_error || 'The analysis worker could not process these games.';
            const nextError = new Error(detail);
            setError(nextError);
            options?.onError?.(nextError);
            return;
          }

          options?.onComplete?.(nextStatus);
        } catch (requestError: unknown) {
          if (cancelledRef.current) return;

          // 401/403 are permanent (bad session / wrong owner) — fail fast.
          // 404 is ambiguous: right after queuing, the job store can lag one
          // poll, so treat it as transient with a tighter budget.
          const statusCode = (requestError as { response?: { status?: number } })?.response?.status;
          const authPermanent = statusCode === 401 || statusCode === 403;
          const is404 = statusCode === 404;

          const failures = authPermanent
            ? MAX_CONSECUTIVE_FAILURES
            : consecutiveFailures + 1;
          const failureBudget = is404 ? MAX_404_BUDGET : MAX_CONSECUTIVE_FAILURES;
          if (failures < failureBudget) {
            // Transient miss — back off and keep polling instead of failing.
            const backoff = Math.min(POLL_INTERVAL_MS * 2 ** failures, MAX_BACKOFF_MS);
            timerRef.current = setTimeout(() => void poll(failures), backoff);
            return;
          }

          const detail = (requestError as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
          const nextError = new Error(
            typeof detail === 'string'
              ? detail
              : is404 && failures >= failureBudget
                ? 'The analysis job could not be found — it may have been dropped while the server was restarting. Try again.'
                : 'Could not retrieve analysis progress. The job may still be running.',
          );
          setError(nextError);
          setIsTracking(false);
          timerRef.current = null;
          options?.onError?.(nextError);
        }
      };

      void poll();
    },
    [stop, userId],
  );

  const cancelJob = useCallback(async () => {
    if (!userId || !status?.job_id) throw new Error('No active analysis job to cancel.');
    const cancelledStatus = await api.analysis.cancelJob(userId, status.job_id);
    stop();
    setError(null);
    setStatus(cancelledStatus);
    return cancelledStatus;
  }, [status?.job_id, stop, userId]);

  useEffect(() => {
    if (!userId || isTracking || status) return;

    let active = true;
    const restoreActiveJob = async () => {
      try {
        const activeJob = await api.analysis.getActiveJobStatus(userId);
        if (!active) return;
        setStatus(activeJob);
        if (!isTerminal(activeJob.status)) watchJob(activeJob.job_id);
      } catch (requestError: unknown) {
        const statusCode = (requestError as { response?: { status?: number } })?.response?.status;
        if (statusCode !== 404) {
          // Recovery is best-effort; starting a new analysis remains available.
          console.warn('Could not restore active analysis job', requestError);
        }
      }
    };

    void restoreActiveJob();
    return () => {
      active = false;
    };
  }, [isTracking, status, userId, watchJob]);

  return {
    status,
    isTracking,
    // Keep this alias for callers using the original stream-oriented name.
    isStreaming: isTracking,
    error,
    watchJob,
    cancelJob,
    watchJobAsync: async (jobId?: string, options?: WatchAnalysisJobOptions) => {
      watchJob(jobId, options);
    },
    stop,
  };
}
