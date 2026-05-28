import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { profileApi } from '@/lib/api';
import { PlayerProfile } from '@/types/profile.types';

const STALE_TIME_MS = 1000 * 60 * 5;

export function usePlayerProfile(userId: number | undefined) {
  return useQuery({
    queryKey: ['player-profile', userId],
    queryFn: async (): Promise<PlayerProfile | undefined> => {
      try {
        return await profileApi.getLatest(userId!);
      } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status === 404) {
          return undefined;
        }
        throw error;
      }
    },
    enabled: !!userId,
    staleTime: STALE_TIME_MS,
    retry: false,
  });
}

export function usePlayerProfileHistory(
  userId: number | undefined,
  options?: { skip?: number; limit?: number },
) {
  const skip = options?.skip ?? 0;
  const limit = options?.limit ?? 50;

  return useQuery({
    queryKey: ['player-profile-history', userId, skip, limit],
    queryFn: () => profileApi.getHistory(userId!, { skip, limit }),
    enabled: !!userId,
    staleTime: STALE_TIME_MS,
  });
}

export function useTriggerProfileBuild() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: number) => profileApi.triggerBuild(userId),
    onSuccess: (_, userId) => {
      queryClient.invalidateQueries({ queryKey: ['player-profile', userId] });
      queryClient.invalidateQueries({ queryKey: ['player-profile-history', userId] });
    },
  });
}
