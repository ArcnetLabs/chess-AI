import api from '@/lib/api';
import { Game, User } from '@/types';
import { AnalyzingGameInfo, toAnalyzingGameInfo } from '@/features/dashboard/utils/gameDisplay';

export interface AnalysisPollingCallbacks {
  onProgress: (analyzedCount: number, currentGame: AnalyzingGameInfo | null) => void;
  onComplete: (analyzedCount: number) => void;
  onTimeout: () => void;
  onError?: (error: unknown) => void;
}

export interface BatchPollingOptions extends AnalysisPollingCallbacks {
  userId: number;
  user: User;
  targetCount: number;
  refetchGames: () => Promise<{ data?: Game[] }>;
  refetchAnalysisSummary: () => Promise<unknown>;
}

export interface SingleGamePollingOptions extends AnalysisPollingCallbacks {
  userId: number;
  gameId: number;
  refetchGames: () => Promise<unknown>;
  refetchAnalysisSummary: () => Promise<unknown>;
}

const BATCH_POLL_INTERVAL_MS = 8000;
const BATCH_MAX_POLLS = 50;
const SINGLE_POLL_INTERVAL_MS = 5000;
const SINGLE_MAX_POLLS = 45;

export function startBatchAnalysisPolling(options: BatchPollingOptions): () => void {
  let pollCount = 0;
  let lastAnalyzedCount = 0;
  let baselineAnalyzed: number | null = null;

  const intervalId = setInterval(async () => {
    pollCount += 1;

    try {
      const gamesResult = await options.refetchGames();
      const updatedGames = gamesResult.data;

      if (!updatedGames) return;

      const analyzedCount = updatedGames.filter((g) => g.is_analyzed).length;
      if (baselineAnalyzed === null) {
        baselineAnalyzed = analyzedCount;
      }
      const newlyAnalyzed = analyzedCount - baselineAnalyzed;
      const unanalyzedGame = updatedGames.find((g) => !g.is_analyzed);
      const currentGame = unanalyzedGame ? toAnalyzingGameInfo(unanalyzedGame, options.user) : null;

      options.onProgress(analyzedCount, currentGame);

      if (analyzedCount > lastAnalyzedCount) {
        await options.refetchAnalysisSummary();
        lastAnalyzedCount = analyzedCount;
      }

      if (pollCount >= BATCH_MAX_POLLS || newlyAnalyzed >= options.targetCount) {
        clearInterval(intervalId);
        options.onComplete(analyzedCount);
      }
    } catch (error) {
      options.onError?.(error);
    }
  }, BATCH_POLL_INTERVAL_MS);

  return () => clearInterval(intervalId);
}

export function startSingleGameAnalysisPolling(options: SingleGamePollingOptions): () => void {
  let pollCount = 0;

  const intervalId = setInterval(async () => {
    pollCount += 1;

    try {
      const updatedGames = await api.games.getForUser(options.userId, { limit: 100 });
      const game = updatedGames.find((g) => g.id === options.gameId);

      if (game?.is_analyzed) {
        clearInterval(intervalId);
        await Promise.all([options.refetchGames(), options.refetchAnalysisSummary()]);
        options.onComplete(1);
        return;
      }

      if (pollCount >= SINGLE_MAX_POLLS) {
        clearInterval(intervalId);
        options.onTimeout();
      }
    } catch (error) {
      options.onError?.(error);
    }
  }, SINGLE_POLL_INTERVAL_MS);

  return () => clearInterval(intervalId);
}
