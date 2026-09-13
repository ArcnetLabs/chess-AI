import { useQuery } from '@tanstack/react-query';
import { gamesApi } from '@/lib/api';
import type { Game } from '@/types';

const STALE_TIME_MS = 1000 * 60;

/**
 * Fetch a user's games through React Query.
 *
 * Why a query instead of a page-local useEffect: the insights page previously
 * fetched inside an effect with no catch and no retry. A single transient
 * miss (deploy bounce, proxy blip, focus churn) left the list empty forever
 * while the backend had answered 200 — the UI silently degraded to
 * "No games yet". Query retries, caches, and refetches on focus, so a blip
 * self-heals without the user reloading.
 */
export function useUserGames(userId: number | undefined, limit = 250) {
  return useQuery({
    queryKey: ['user-games', userId, limit],
    queryFn: async (): Promise<Game[]> => {
      const games = await gamesApi.getForUser(userId!, { limit });
      if (!Array.isArray(games)) {
        throw new Error('Unexpected games response shape from the API.');
      }
      return [...games].sort((a, b) => {
        const aTime = a.end_time ? Date.parse(a.end_time) : 0;
        const bTime = b.end_time ? Date.parse(b.end_time) : 0;
        return bTime - aTime;
      });
    },
    enabled: !!userId,
    staleTime: STALE_TIME_MS,
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
    refetchOnWindowFocus: true,
  });
}
