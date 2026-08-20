import { useEffect } from 'react';
import chatService from '@/services/chatService';
import { useChatStore } from '@/store/chatStore';

/**
 * Ensures the floating chatbot session is tied to the authenticated ChessIQ user.
 */
export function useChatSession(userId: number | undefined) {
  const restoreSession = useChatStore((state) => state.restoreSession);
  const sessionId = useChatStore((state) => state.sessionId);

  useEffect(() => {
    chatService.setUserId(userId);
  }, [userId]);

  useEffect(() => {
    if (!userId || sessionId) return;
    restoreSession(userId);
  }, [userId, sessionId, restoreSession]);
}
