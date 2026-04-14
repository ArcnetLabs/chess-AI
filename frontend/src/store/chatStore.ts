/**
 * Chat State Management using Zustand
 */

import { create } from 'zustand';
import { Message, ChatResponse } from '@/types/chat.types';
import chatService from '@/services/chatService';

interface ChatState {
  // UI State
  isOpen: boolean;
  isMinimized: boolean;
  
  // Session State
  sessionId: string | null;
  messages: Message[];
  isTyping: boolean;
  unreadCount: number;
  
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
  loadHistory: () => Promise<void>;
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
  messages: [],
  isTyping: false,
  unreadCount: 0,
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
      set({ error: null });
      const response = await chatService.createSession(userId);
      
      set({ 
        sessionId: response.session_id,
        messages: [{
          id: `welcome-${Date.now()}`,
          role: 'assistant',
          content: response.message,
          timestamp: new Date(),
        }]
      });
    } catch (error) {
      console.error('Failed to initialize session:', error);
      set({ error: 'Failed to start chat session. Please try again.' });
    }
  },

  loadHistory: async () => {
    try {
      const history = await chatService.getHistory(20);
      set({ messages: history });
    } catch (error) {
      console.error('Failed to load history:', error);
    }
  },

  clearChat: async () => {
    try {
      await chatService.deleteSession();
      set({ 
        sessionId: null,
        messages: [],
        currentPosition: null,
        error: null,
      });
    } catch (error) {
      console.error('Failed to clear chat:', error);
    }
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
        positionFen || state.currentPosition || undefined
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
        },
      };

      set(state => ({ 
        messages: [...state.messages, assistantMessage],
        isTyping: false,
        sessionId: response.session_id,
        // Increment unread if chat is closed
        unreadCount: state.isOpen ? 0 : state.unreadCount + 1,
      }));

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
