import { useQuery } from '@tanstack/react-query';
import { profileApi } from '@/lib/api';
import { PlayerProfile } from '@/types/profile.types';

const STALE_TIME_MS = 1000 * 60 * 5;

export function usePlayerProfile(userId: number | undefined) {
  return useQuery({
    queryKey: ['player-profile', userId],
    queryFn: async (): Promise<PlayerProfile | undefined> => {
      // `null` is "no snapshot yet" — the backend answers 204 No Content while a
      // brand-new account is still onboarding, so this resolves with no data
      // instead of erroring the query on a normal state.
      return (await profileApi.getLatest(userId!)) ?? undefined;
    },
    enabled: !!userId,
    staleTime: STALE_TIME_MS,
    retry: false,
  });
}