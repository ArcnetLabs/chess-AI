/**
 * Chat Window Component
 * Main popup container for the chat interface
 */

import React, { useEffect } from 'react';
import { useChatStore } from '@/store/chatStore';
import { ChatHeader } from './ChatHeader';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';

export const ChatWindow: React.FC = () => {
  const { isOpen, isMinimized, error, setError } = useChatStore();

  // Don't render if not open
  if (!isOpen) {
    return null;
  }

  // Minimized state
  if (isMinimized) {
    return (
      <div className="
        fixed bottom-6 right-6 z-50
        w-64 bg-white rounded-lg shadow-lg
        border border-gray-200
      ">
        <ChatHeader />
      </div>
    );
  }

  return (
    <>
      {/* Backdrop (optional, for mobile) */}
      <div 
        className="
          fixed inset-0 bg-black/20 z-40
          md:hidden
        "
        onClick={() => useChatStore.getState().closeChat()}
      />

      {/* Chat Window */}
      <div className="
        fixed z-50
        bottom-6 right-6
        w-[380px] h-[600px]
        max-w-[calc(100vw-32px)]
        max-h-[80vh]
        bg-white
        rounded-2xl
        shadow-2xl
        border border-gray-200
        flex flex-col
        animate-slideUp
      ">
        {/* Header */}
        <ChatHeader />

        {/* Error Banner */}
        {error && (
          <div className="
            mx-4 mt-3 p-3
            bg-red-50 border border-red-200
            rounded-lg
            flex items-start gap-2
          ">
            <svg 
              className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" 
              />
            </svg>
            <div className="flex-1">
              <p className="text-sm text-red-800">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-500 hover:text-red-700"
            >
              <svg 
                className="w-4 h-4" 
                fill="none" 
                stroke="currentColor" 
                viewBox="0 0 24 24"
              >
                <path 
                  strokeLinecap="round" 
                  strokeLinejoin="round" 
                  strokeWidth={2} 
                  d="M6 18L18 6M6 6l12 12" 
                />
              </svg>
            </button>
          </div>
        )}

        {/* Messages */}
        <MessageList />

        {/* Input */}
        <ChatInput />
      </div>
    </>
  );
};

export default ChatWindow;
