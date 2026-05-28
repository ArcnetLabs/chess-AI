import { useCallback, useEffect, useRef, useState } from 'react';
import type { AnalysisJobStatus } from '@/types/analysis.types';
import {
  type AnalysisStatusStreamCallbacks,
  startAnalysisStatusStream,
  subscribeAnalysisStatus,
} from '@/services/analysisStatusService';

export interface WatchAnalysisJobOptions {
  onProgress?: (status: AnalysisJobStatus) => void;
  onComplete?: (status: AnalysisJobStatus) => void;
  onError?: (error: Error) => void;
  onTimeout?: (status: AnalysisJobStatus) => void;
}

export function useAnalysisStatus(userId: number | undefined) {
  const [status, setStatus] = useState<AnalysisJobStatus | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const stopRef = useRef<(() => void) | null>(null);

  const stop = useCallback(() => {
    stopRef.current?.();
    stopRef.current = null;
    setIsStreaming(false);
  }, []);

  useEffect(() => stop, [stop]);

  const watchJob = useCallback(
    (jobId?: string, options?: WatchAnalysisJobOptions) => {
      if (!userId) {
        return;
      }

      stop();
      setError(null);
      setIsStreaming(true);

      const callbacks: AnalysisStatusStreamCallbacks = {
        onProgress: (jobStatus) => {
          setStatus(jobStatus);
          options?.onProgress?.(jobStatus);
        },
        onComplete: (jobStatus) => {
          setStatus(jobStatus);
          setIsStreaming(false);
          stopRef.current = null;
          options?.onComplete?.(jobStatus);
        },
        onError: (streamError) => {
          setError(streamError);
          setIsStreaming(false);
          stopRef.current = null;
          options?.onError?.(streamError);
        },
        onTimeout: (jobStatus) => {
          setStatus(jobStatus);
          setIsStreaming(false);
          stopRef.current = null;
          options?.onTimeout?.(jobStatus);
        },
      };

      stopRef.current = startAnalysisStatusStream(userId, jobId, callbacks);
    },
    [userId, stop],
  );

  const watchJobAsync = useCallback(
    async (jobId?: string, options?: WatchAnalysisJobOptions) => {
      if (!userId) {
        return;
      }

      stop();
      setError(null);
      setIsStreaming(true);

      stopRef.current = await subscribeAnalysisStatus(
        userId,
        {
          onProgress: (jobStatus) => {
            setStatus(jobStatus);
            options?.onProgress?.(jobStatus);
          },
          onComplete: (jobStatus) => {
            setStatus(jobStatus);
            setIsStreaming(false);
            stopRef.current = null;
            options?.onComplete?.(jobStatus);
          },
          onError: (streamError) => {
            setError(streamError);
            setIsStreaming(false);
            stopRef.current = null;
            options?.onError?.(streamError);
          },
          onTimeout: (jobStatus) => {
            setStatus(jobStatus);
            setIsStreaming(false);
            stopRef.current = null;
            options?.onTimeout?.(jobStatus);
          },
        },
        jobId,
      );
    },
    [userId, stop],
  );

  return {
    status,
    isStreaming,
    error,
    watchJob,
    watchJobAsync,
    stop,
  };
}
