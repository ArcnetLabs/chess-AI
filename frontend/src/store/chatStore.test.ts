import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useChatStore } from './chatStore';

const chatServiceMock = vi.hoisted(() => ({
  setUserId: vi.fn(),
  createSession: vi.fn(),
  listSessions: vi.fn(),
  setSessionId: vi.fn(),
  getHistory: vi.fn(),
  sendMessage: vi.fn(),
}));

vi.mock('@/services/chatService', () => ({
  default: chatServiceMock,
}));

const initialState = useChatStore.getState();

function resetStore() {
  useChatStore.setState(initialState, true);
  vi.clearAllMocks();
}

describe('chatStore', () => {
  beforeEach(resetStore);

  describe('restoreSession', () => {
    it('restores the remembered session when it still exists', async () => {
      chatServiceMock.listSessions.mockResolvedValue([
        { session_id: 'remembered', preview: 'Remembered chat' },
        { session_id: 'other', preview: 'Other chat' },
      ]);
      chatServiceMock.getHistory.mockResolvedValue([
        {
          id: 'm1',
          role: 'assistant',
          content: 'Welcome back',
          timestamp: new Date().toISOString(),
        },
      ]);
      window.localStorage.setItem('chessrun:active-chat:7', 'remembered');

      await useChatStore.getState().restoreSession(7);

      const state = useChatStore.getState();
      expect(chatServiceMock.setSessionId).toHaveBeenCalledWith('remembered');
      expect(state.sessionId).toBe('remembered');
      expect(state.messages[0].content).toBe('Welcome back');
      expect(state.isRestoringSession).toBe(false);
    });

    it('initializes a new session when no sessions exist', async () => {
      chatServiceMock.listSessions.mockResolvedValue([]);
      chatServiceMock.createSession.mockResolvedValue({
        session_id: 'fresh',
        message: 'Hello! I am your coach.',
      });

      await useChatStore.getState().restoreSession(7);

      const state = useChatStore.getState();
      expect(state.sessionId).toBe('fresh');
      expect(state.messages[0].role).toBe('assistant');
      expect(state.messages[0].content).toBe('Hello! I am your coach.');
    });

    it('falls back to another session when the remembered one is gone', async () => {
      chatServiceMock.listSessions.mockResolvedValue([
        { session_id: 'a', preview: 'A' },
        { session_id: 'b', preview: 'B' },
      ]);
      chatServiceMock.getHistory
        .mockRejectedValueOnce(new Error('gone'))
        .mockResolvedValueOnce([
          {
            id: 'm1',
            role: 'assistant',
            content: 'Fallback',
            timestamp: new Date().toISOString(),
          },
        ]);
      window.localStorage.setItem('chessrun:active-chat:7', 'missing');

      await useChatStore.getState().restoreSession(7);

      expect(useChatStore.getState().sessionId).toBe('b');
      expect(useChatStore.getState().messages[0].content).toBe('Fallback');
    });
  });

  describe('sendMessage', () => {
    it('appends the user message and the assistant reply', async () => {
      chatServiceMock.createSession.mockResolvedValue({
        session_id: 's1',
        message: 'Welcome',
      });
      chatServiceMock.listSessions.mockResolvedValue([]);
      chatServiceMock.sendMessage.mockResolvedValue({
        session_id: 's1',
        response: {
          message: 'Good question!',
          intent: 'analysis',
          suggestions: [],
          used_llm: true,
          llm_provider: 'mock',
          cited_pattern_ids: [],
        },
      });

      await useChatStore.getState().initializeSession(7);
      await useChatStore.getState().sendMessage('Why do I blunder in time trouble?');

      const { messages, isTyping, error } = useChatStore.getState();
      expect(messages).toHaveLength(3);
      expect(messages[1]).toMatchObject({ role: 'user', content: 'Why do I blunder in time trouble?' });
      expect(messages[2]).toMatchObject({ role: 'assistant', content: 'Good question!' });
      expect(isTyping).toBe(false);
      expect(error).toBeNull();
    });

    it('records an error when the backend call fails', async () => {
      chatServiceMock.createSession.mockResolvedValue({
        session_id: 's1',
        message: 'Welcome',
      });
      chatServiceMock.listSessions.mockResolvedValue([]);
      chatServiceMock.sendMessage.mockRejectedValue(new Error('network down'));

      await useChatStore.getState().initializeSession(7);
      await useChatStore.getState().sendMessage('hello');

      const state = useChatStore.getState();
      expect(state.isTyping).toBe(false);
      expect(state.error).toBe('Failed to send message. Please try again.');
      expect(state.messages).toHaveLength(2);
    });
  });
});