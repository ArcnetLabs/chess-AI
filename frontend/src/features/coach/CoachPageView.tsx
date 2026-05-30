import React, { useEffect } from 'react';
import { ChessrunPageShell } from '@/components/layout/ChessrunPageShell';
import { ChatHeader } from '@/components/chat/ChatHeader';
import { MessageList } from '@/components/chat/MessageList';
import { ChatInput } from '@/components/chat/ChatInput';
import { DashboardLoadingState, DashboardErrorState } from '@/components/dashboard';
import { useChatSession, useCurrentUser } from '@/hooks';
import { useChatStore } from '@/store/chatStore';
import { useRouter } from 'next/router';

export const CoachPageView: React.FC = () => {
  const router = useRouter();
  const { user, loading, refetchUser } = useCurrentUser();
  const initializeSession = useChatStore((s) => s.initializeSession);
  const error = useChatStore((s) => s.error);
  const setError = useChatStore((s) => s.setError);

  useChatSession(user?.id);

  useEffect(() => {
    if (!user?.id) return;
    const state = useChatStore.getState();
    if (!state.sessionId) {
      initializeSession(user.id);
    }
    useChatStore.setState({ isOpen: true, isMinimized: false });
  }, [user?.id, initializeSession]);

  if (loading) {
    return <DashboardLoadingState />;
  }

  if (!user) {
    return (
      <DashboardErrorState
        onGoHome={() => router.push('/auth/login')}
        onRetry={() => refetchUser()}
      />
    );
  }

  return (
    <ChessrunPageShell
      title="AI Coach"
      subtitle="Ask questions about your games, openings, and improvement plan."
      maxWidth="xl"
    >
      <div className="flex h-[min(70vh,640px)] flex-col overflow-hidden rounded-chess-md bg-surface-container shadow-brand-ambient">
        <ChatHeader />
        {error && (
          <div className="mx-4 mt-3 flex items-start gap-2 rounded-chess bg-brand-error/10 p-3 text-sm text-brand-error">
            <span className="flex-1">{error}</span>
            <button
              type="button"
              onClick={() => setError(null)}
              className="text-content-muted hover:text-content"
            >
              Dismiss
            </button>
          </div>
        )}
        <MessageList />
        <ChatInput />
      </div>
    </ChessrunPageShell>
  );
};
