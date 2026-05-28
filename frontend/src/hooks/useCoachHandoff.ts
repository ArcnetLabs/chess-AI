import { useCallback, useState } from 'react';
import api from '@/lib/api';
import chatService from '@/services/chatService';
import { useChatStore } from '@/store/chatStore';
import type { CoachHandoffResponse } from '@/types';

export interface CoachHandoffOptions {
  moveNumber?: number;
  primeSession?: boolean;
  openChat?: boolean;
}

/**
 * Hand off a game position to the floating coach (P2-GV-04).
 * Sets chat FEN context and optionally primes a new backend session.
 */
export function useCoachHandoff() {
  const setCurrentPosition = useChatStore((state) => state.setCurrentPosition);
  const openChat = useChatStore((state) => state.openChat);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [lastHandoff, setLastHandoff] = useState<CoachHandoffResponse | null>(null);

  const handoffToCoach = useCallback(
    async (gameId: number, options?: CoachHandoffOptions) => {
      setIsLoading(true);
      setError(null);

      try {
        const result = await api.games.coachHandoff(gameId, {
          move_number: options?.moveNumber,
          prime_session: options?.primeSession ?? true,
        });

        setCurrentPosition(result.fen);
        setLastHandoff(result);

        if (result.session_id) {
          chatService.setSessionId(result.session_id);
          useChatStore.setState({ sessionId: result.session_id });
        }

        if (options?.openChat !== false) {
          openChat();
        }

        return result;
      } catch (handoffError) {
        const normalized =
          handoffError instanceof Error
            ? handoffError
            : new Error('Failed to hand off position to coach');
        setError(normalized);
        throw normalized;
      } finally {
        setIsLoading(false);
      }
    },
    [openChat, setCurrentPosition],
  );

  return {
    handoffToCoach,
    isLoading,
    error,
    lastHandoff,
  };
}

export default useCoachHandoff;
