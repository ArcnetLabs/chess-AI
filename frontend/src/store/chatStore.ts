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
  // UI State
  isOpen: boolean;
  isMinimized: boolean;
  
  // Session State
  sessionId: string | null;
  userId: number | undefined;
  messages: Message[];
  isTyping: boolean;
  unreadCount: number;
  recentSessions: ChatSessionSummary[];
  isLoadingSessions: boolean;
  isRestoringSession: boolean;
  
  // Context
  currentPosition: string | null;
  
  // Error State
  error: string | null;
  
  // Actions
  openChat: () => void;
  closeChat: () => void;
  toggleChat: () => void;
  minimizeChat: () => void;
  maximizeChat: () => void;
  
  sendMessage: (content: string, positionFen?: string) => Promise<void>;
  initializeSession: (userId?: number) => Promise<void>;
  restoreSession: (userId: number) => Promise<void>;
  openSession: (sessionId: string) => Promise<void>;
  refreshSessions: () => Promise<void>;
  clearChat: () => Promise<void>;
  
  setCurrentPosition: (fen: string | null) => void;
  markAsRead: () => void;
  addMessage: (message: Message) => void;
  setError: (error: string | null) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  // Initial State
  isOpen: false,
  isMinimized: false,
  sessionId: null,
  userId: undefined,
  messages: [],
  isTyping: false,
  unreadCount: 0,
  recentSessions: [],
  isLoadingSessions: false,
  isRestoringSession: false,
  currentPosition: null,
  error: null,

  // UI Actions
  openChat: () => {
    set({ isOpen: true, isMinimized: false, unreadCount: 0 });
    
    // Initialize session if not exists
    const state = get();
    if (!state.sessionId) {
      state.initializeSession();
    }
  },

  closeChat: () => {
    set({ isOpen: false, isMinimized: false });
  },

  toggleChat: () => {
    const state = get();
    if (state.isOpen) {
      state.closeChat();
    } else {
      state.openChat();
    }
  },

  minimizeChat: () => {
    set({ isMinimized: true });
  },

  maximizeChat: () => {
    set({ isMinimized: false });
  },

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

  clearChat: async () => {
    // Starting a new chat must not delete the existing coaching thread.
    chatService.setSessionId('');
    writeActiveSession(get().userId, null);
    set({ sessionId: null, messages: [], currentPosition: null, error: null });
  },

  // Message Actions
  sendMessage: async (content: string, positionFen?: string) => {
    const state = get();
    
    // Add user message immediately
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
      position_fen: positionFen || state.currentPosition || undefined,
    };
    
    set({ 
      messages: [...state.messages, userMessage],
      isTyping: true,
      error: null,
    });

    try {
      // Send to backend
      const response = await chatService.sendMessage(
        content,
        positionFen || state.currentPosition || undefined,
        state.userId,
      );

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
        // Increment unread if chat is closed
        unreadCount: state.isOpen ? 0 : state.unreadCount + 1,
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

  addMessage: (message: Message) => {
    set(state => ({ 
      messages: [...state.messages, message],
      unreadCount: state.isOpen ? 0 : state.unreadCount + 1,
    }));
  },

  // Context Actions
  setCurrentPosition: (fen: string | null) => {
    set({ currentPosition: fen });
  },

  markAsRead: () => {
    set({ unreadCount: 0 });
  },

  setError: (error: string | null) => {
    set({ error });
  },
}));

export default useChatStore;
