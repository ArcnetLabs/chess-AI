import { useEffect } from 'react';
import chatService from '@/services/chatService';
import { useChatStore } from '@/store/chatStore';

/**
 * Ensures the floating chatbot session is tied to the authenticated ChessIQ user.
 */
export function useChatSession(userId: number | undefined) {
  const initializeSession = useChatStore((state) => state.initializeSession);
  const sessionId = useChatStore((state) => state.sessionId);

  useEffect(() => {
    chatService.setUserId(userId);
  }, [userId]);

  useEffect(() => {
    if (!userId || sessionId) return;
    initializeSession(userId);
  }, [userId, sessionId, initializeSession]);
}
