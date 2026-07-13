/**
 * Chat API Service — thin wrapper over lib/api.ts chat endpoints.
 * Keeps session state local; all HTTP goes through the shared axios client.
 */

import api from '@/lib/api';
import { ChatSessionSummary, Message } from '@/types/chat.types';

class ChatService {
  private sessionId: string | null = null;
  private userId: number | undefined;

  setUserId(userId: number | undefined) {
    this.userId = userId;
  }

  async createSession(userId?: number): Promise<{ session_id: string; message: string }> {
    const resolvedUserId = userId ?? this.userId;
    const data = await api.chat.createSession(
      resolvedUserId !== undefined ? { user_id: resolvedUserId } : undefined,
    );
    this.sessionId = data.session_id;
    return { session_id: data.session_id, message: data.message };
  }

  async sendMessage(
    message: string,
    positionFen?: string,
    userId?: number,
  ): Promise<Awaited<ReturnType<typeof api.chat.sendMessage>>> {
    const data = await api.chat.sendMessage({
      message,
      session_id: this.sessionId || undefined,
      user_id: userId ?? this.userId,
      position_fen: positionFen,
    });

    if (data.session_id) {
      this.sessionId = data.session_id;
    }

    return data;
  }

  async getHistory(limit = 200): Promise<Message[]> {
    if (!this.sessionId) {
      return [];
    }
    return api.chat.getHistory(this.sessionId, limit);
  }

  async listSessions(limit = 50): Promise<ChatSessionSummary[]> {
    const response = await api.chat.listSessions(limit);
    return response.sessions;
  }

  async deleteSession(): Promise<void> {
    if (!this.sessionId) {
      return;
    }
    await api.chat.deleteSession(this.sessionId);
    this.sessionId = null;
  }

  async quickAnalysis(positionFen: string) {
    return api.chat.quickAnalysis(positionFen);
  }

  getSessionId(): string | null {
    return this.sessionId;
  }

  setSessionId(sessionId: string): void {
    this.sessionId = sessionId;
  }

  hasSession(): boolean {
    return this.sessionId !== null;
  }
}

export const chatService = new ChatService();
export default chatService;
