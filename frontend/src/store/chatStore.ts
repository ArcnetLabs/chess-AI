/**
 * Chat State Management using Zustand
 */

import { create } from 'zustand';
import { ChatSessionSummary, Message } from '@/types/chat.types';
import chatService from '@/services/chatService';

const activeSessionKey = (userId: number) => `chessrun:active-chat:${userId}`;

function readActiveSession(userId: number): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(activeSessionKey(userId));
}

function writeActiveSession(userId: number | undefined, sessionId: string | null) {
  if (typeof window === 'undefined' || !userId) return;
  if (sessionId) window.localStorage.setItem(activeSessionKey(userId), sessionId);
  else window.localStorage.removeItem(activeSessionKey(userId));
}

interface ChatState {
  // Session State
  sessionId: string | null;
  userId: number | undefined;
  messages: Message[];
  isTyping: boolean;
  recentSessions: ChatSessionSummary[];
  isLoadingSessions: boolean;
  isRestoringSession: boolean;

  // Error State
  error: string | null;

  // Actions
  sendMessage: (content: string) => Promise<void>;
  initializeSession: (userId?: number) => Promise<void>;
  restoreSession: (userId: number) => Promise<void>;
  openSession: (sessionId: string) => Promise<void>;
  refreshSessions: () => Promise<void>;
  setError: (error: string | null) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  // Initial State
  sessionId: null,
  userId: undefined,
  messages: [],
  isTyping: false,
  recentSessions: [],
  isLoadingSessions: false,
  isRestoringSession: false,
  error: null,

  // Session Actions
  initializeSession: async (userId?: number) => {
    try {
      const resolvedUserId = userId ?? get().userId;
      set({ error: null, userId: resolvedUserId });
      chatService.setUserId(resolvedUserId);
      const response = await chatService.createSession(resolvedUserId);

      set({
        sessionId: response.session_id,
        messages: [{
          id: `welcome-${Date.now()}`,
          role: 'assistant',
          content: response.message,
          timestamp: new Date(),
        }]
      });
      writeActiveSession(resolvedUserId, response.session_id);
      await get().refreshSessions();
    } catch (error) {
      console.error('Failed to initialize session:', error);
      set({ error: 'Failed to start chat session. Please try again.' });
    }
  },

  refreshSessions: async () => {
    try {
      set({ isLoadingSessions: true });
      const recentSessions = await chatService.listSessions();
      set({ recentSessions });
    } catch (error) {
      console.error('Failed to load chat sessions:', error);
    } finally {
      set({ isLoadingSessions: false });
    }
  },

  openSession: async (sessionId: string) => {
    try {
      chatService.setSessionId(sessionId);
      const history = await chatService.getHistory(200);
      set({ sessionId, messages: history, error: null });
      writeActiveSession(get().userId, sessionId);
    } catch (error) {
      console.error('Failed to restore chat history:', error);
      set({ error: 'Could not restore this conversation.' });
      throw error;
    }
  },

  restoreSession: async (userId: number) => {
    const state = get();
    if (state.sessionId || state.isRestoringSession) return;

    set({ userId, error: null, isRestoringSession: true });
    chatService.setUserId(userId);
    try {
      const recentSessions = await chatService.listSessions();
      set({ recentSessions });
      const rememberedId = readActiveSession(userId);
      const rememberedSession = recentSessions.find(
        (session) => session.session_id === rememberedId,
      );
      const sessionToRestore = rememberedSession ?? recentSessions[0];
      if (sessionToRestore) {
        try {
          await get().openSession(sessionToRestore.session_id);
        } catch {
          writeActiveSession(userId, null);
          const fallback = recentSessions.find(
            (session) => session.session_id !== sessionToRestore.session_id,
          );
          if (fallback) await get().openSession(fallback.session_id);
          else await get().initializeSession(userId);
        }
      } else {
        await get().initializeSession(userId);
      }
    } catch (error) {
      console.error('Failed to restore chat session:', error);
      set({ error: 'Could not restore your coaching conversation.' });
    } finally {
      set({ isRestoringSession: false });
    }
  },

  // Message Actions
  sendMessage: async (content: string) => {
    const state = get();

    // Add user message immediately
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
    };

    set({
      messages: [...state.messages, userMessage],
      isTyping: true,
      error: null,
    });

    try {
      // Send to backend
      const response = await chatService.sendMessage(content, undefined, state.userId);

      // Add assistant response
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.response.message,
        timestamp: new Date(),
        intent: response.response.intent,
        position_fen: response.response.position_fen,
        metadata: {
          analysis: response.response.analysis,
          suggestions: response.response.suggestions,
          used_llm: response.response.used_llm,
          llm_provider: response.response.llm_provider,
          cited_pattern_ids: response.response.cited_pattern_ids,
        },
      };

      set(state => ({
        messages: [...state.messages, assistantMessage],
        isTyping: false,
        sessionId: response.session_id,
      }));
      writeActiveSession(get().userId, response.session_id);
      await get().refreshSessions();

    } catch (error) {
      console.error('Failed to send message:', error);
      set({
        isTyping: false,
        error: 'Failed to send message. Please try again.',
      });
    }
  },

  setError: (error: string | null) => {
    set({ error });
  },
}));

export default useChatStore;