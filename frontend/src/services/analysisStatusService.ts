import { createClient } from '@/lib/supabase/client';
import type { AnalysisJobStatus } from '@/types/analysis.types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface AnalysisStatusStreamCallbacks {
  onProgress: (status: AnalysisJobStatus) => void;
  onComplete: (status: AnalysisJobStatus) => void;
  onError: (error: Error) => void;
  onTimeout?: (status: AnalysisJobStatus) => void;
}

async function getAccessToken(): Promise<string | null> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

function parseSseFrame(frame: string): { event: string; data: unknown } | null {
  let event = 'message';
  let dataLine = '';

  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      dataLine = line.slice(5).trim();
    }
  }

  if (!dataLine) {
    return null;
  }

  return { event, data: JSON.parse(dataLine) };
}

/**
 * Subscribe to analysis job progress via SSE (fetch + Authorization header).
 * Returns an abort function to close the stream.
 */
export async function subscribeAnalysisStatus(
  userId: number,
  callbacks: AnalysisStatusStreamCallbacks,
  jobId?: string,
): Promise<() => void> {
  const token = await getAccessToken();
  if (!token) {
    callbacks.onError(new Error('Not authenticated'));
    return () => {};
  }

  const url = new URL(`${API_BASE_URL}/api/v1/analysis/${userId}/status/stream`);
  if (jobId) {
    url.searchParams.set('job_id', jobId);
  }

  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(url.toString(), {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'text/event-stream',
        },
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Analysis status stream failed (${response.status})`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Analysis status stream returned no body');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split('\n\n');
        buffer = frames.pop() ?? '';

        for (const frame of frames) {
          if (!frame.trim()) {
            continue;
          }

          const parsed = parseSseFrame(frame);
          if (!parsed) {
            continue;
          }

          if (parsed.event === 'progress') {
            callbacks.onProgress(parsed.data as AnalysisJobStatus);
          } else if (parsed.event === 'done') {
            callbacks.onComplete(parsed.data as AnalysisJobStatus);
            return;
          } else if (parsed.event === 'error') {
            const detail = (parsed.data as { detail?: string }).detail ?? 'Stream error';
            callbacks.onError(new Error(detail));
            return;
          } else if (parsed.event === 'timeout') {
            callbacks.onTimeout?.(parsed.data as AnalysisJobStatus);
            return;
          }
        }
      }
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        callbacks.onError(error as Error);
      }
    }
  })();

  return () => controller.abort();
}

/**
 * Start watching a job; returns a synchronous stop handle (safe before subscribe resolves).
 */
export function startAnalysisStatusStream(
  userId: number,
  jobId: string | undefined,
  callbacks: AnalysisStatusStreamCallbacks,
): () => void {
  let stopStream: (() => void) | null = null;
  let cancelled = false;

  subscribeAnalysisStatus(userId, callbacks, jobId).then((stop) => {
    if (cancelled) {
      stop();
    } else {
      stopStream = stop;
    }
  });

  return () => {
    cancelled = true;
    stopStream?.();
  };
}
