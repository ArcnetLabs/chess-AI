/**
 * Chat API Service
 * Handles all communication with the backend chat API
 */

import {
  SendMessageRequest,
  SendMessageResponse,
  CreateSessionRequest,
  CreateSessionResponse,
  ChatHistoryResponse,
  Message,
} from '@/types/chat.types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const CHAT_API_URL = `${API_BASE_URL}/api/v1/chat`;

class ChatService {
  private sessionId: string | null = null;

  /**
   * Create a new chat session
   */
  async createSession(userId?: number): Promise<CreateSessionResponse> {
    try {
      const response = await fetch(`${CHAT_API_URL}/session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId } as CreateSessionRequest),
      });

      if (!response.ok) {
        throw new Error(`Failed to create session: ${response.statusText}`);
      }

      const data: CreateSessionResponse = await response.json();
      this.sessionId = data.session_id;
      return data;
    } catch (error) {
      console.error('Error creating chat session:', error);
      throw error;
    }
  }

  /**
   * Send a message to the chat
   */
  async sendMessage(
    message: string,
    positionFen?: string,
    userId?: number
  ): Promise<SendMessageResponse> {
    try {
      const requestBody: SendMessageRequest = {
        message,
        session_id: this.sessionId || undefined,
        user_id: userId,
        position_fen: positionFen,
      };

      const response = await fetch(`${CHAT_API_URL}/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error(`Failed to send message: ${response.statusText}`);
      }

      const data: SendMessageResponse = await response.json();
      
      // Update session ID if it changed
      if (data.session_id) {
        this.sessionId = data.session_id;
      }

      return data;
    } catch (error) {
      console.error('Error sending message:', error);
      throw error;
    }
  }

  /**
   * Get conversation history
   */
  async getHistory(limit: number = 20): Promise<Message[]> {
    if (!this.sessionId) {
      return [];
    }

    try {
      const response = await fetch(
        `${CHAT_API_URL}/session/${this.sessionId}/history?limit=${limit}`
      );

      if (!response.ok) {
        throw new Error(`Failed to get history: ${response.statusText}`);
      }

      const data: ChatHistoryResponse = await response.json();
      
      // Convert timestamp strings to Date objects
      return data.messages.map(msg => ({
        ...msg,
        timestamp: new Date(msg.timestamp),
      }));
    } catch (error) {
      console.error('Error getting chat history:', error);
      return [];
    }
  }

  /**
   * Delete the current session
   */
  async deleteSession(): Promise<void> {
    if (!this.sessionId) {
      return;
    }

    try {
      const response = await fetch(`${CHAT_API_URL}/session/${this.sessionId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error(`Failed to delete session: ${response.statusText}`);
      }

      this.sessionId = null;
    } catch (error) {
      console.error('Error deleting session:', error);
      throw error;
    }
  }

  /**
   * Quick position analysis without session
   */
  async quickAnalysis(positionFen: string): Promise<SendMessageResponse> {
    try {
      const response = await fetch(`${CHAT_API_URL}/quick-analysis`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ position_fen: positionFen }),
      });

      if (!response.ok) {
        throw new Error(`Failed to analyze position: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error analyzing position:', error);
      throw error;
    }
  }

  /**
   * Get current session ID
   */
  getSessionId(): string | null {
    return this.sessionId;
  }

  /**
   * Set session ID (for restoring sessions)
   */
  setSessionId(sessionId: string): void {
    this.sessionId = sessionId;
  }

  /**
   * Check if session exists
   */
  hasSession(): boolean {
    return this.sessionId !== null;
  }
}

// Export singleton instance
export const chatService = new ChatService();
export default chatService;
