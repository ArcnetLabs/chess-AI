import { Game, User } from '@/types';
import { AnalyzingGameInfo, toAnalyzingGameInfo } from '@/features/dashboard/utils/gameDisplay';
import type { AnalysisJobStatus } from '@/types/analysis.types';
import { startAnalysisStatusStream } from '@/services/analysisStatusService';

export interface AnalysisPollingCallbacks {
  onProgress: (analyzedCount: number, currentGame: AnalyzingGameInfo | null) => void;
  onComplete: (analyzedCount: number) => void;
  onTimeout: () => void;
  onError?: (error: unknown) => void;
}

export interface BatchPollingOptions extends AnalysisPollingCallbacks {
  userId: number;
  user: User;
  jobId?: string;
  refetchGames: () => Promise<{ data?: Game[] }>;
  refetchAnalysisSummary: () => Promise<unknown>;
}

export interface SingleGamePollingOptions extends AnalysisPollingCallbacks {
  userId: number;
  gameId: number;
  jobId?: string;
  user: User;
  games?: Game[];
  refetchGames: () => Promise<unknown>;
  refetchAnalysisSummary: () => Promise<unknown>;
}

function processedCount(status: AnalysisJobStatus): number {
  return status.completed_games + status.failed_games;
}

function resolveCurrentGame(
  status: AnalysisJobStatus,
  user: User,
  games?: Game[],
): AnalyzingGameInfo | null {
  if (!status.current_game_id || !games) {
    return null;
  }
  const game = games.find((g) => g.id === status.current_game_id);
  return game ? toAnalyzingGameInfo(game, user) : null;
}

export function startBatchAnalysisPolling(options: BatchPollingOptions): () => void {
  let lastProcessed = 0;

  return startAnalysisStatusStream(
    options.userId,
    options.jobId,
    {
      onProgress: async (status) => {
        const gamesResult = await options.refetchGames();
        const currentGame = resolveCurrentGame(status, options.user, gamesResult.data);

        if (status.completed_games > lastProcessed) {
          await options.refetchAnalysisSummary();
          lastProcessed = status.completed_games;
        }

        options.onProgress(processedCount(status), currentGame);
      },
      onComplete: async (status) => {
        await Promise.all([options.refetchGames(), options.refetchAnalysisSummary()]);
        options.onComplete(processedCount(status));
      },
      onTimeout: () => {
        options.onTimeout();
      },
      onError: (error) => {
        options.onError?.(error);
      },
    },
  );
}

export function startSingleGameAnalysisPolling(options: SingleGamePollingOptions): () => void {
  return startAnalysisStatusStream(
    options.userId,
    options.jobId,
    {
      onProgress: async (status) => {
        const gamesResult = await options.refetchGames();
        const updatedGames =
          gamesResult && typeof gamesResult === 'object' && 'data' in gamesResult
            ? (gamesResult as { data?: Game[] }).data
            : options.games;
        const currentGame = resolveCurrentGame(status, options.user, updatedGames);
        options.onProgress(processedCount(status), currentGame);
      },
      onComplete: async (status) => {
        await Promise.all([options.refetchGames(), options.refetchAnalysisSummary()]);
        options.onComplete(processedCount(status));
      },
      onTimeout: () => {
        options.onTimeout();
      },
      onError: (error) => {
        options.onError?.(error);
      },
    },
  );
}
