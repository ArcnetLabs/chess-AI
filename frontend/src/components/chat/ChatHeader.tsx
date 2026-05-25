/**
 * Chat Header Component
 * Title bar with controls
 */

import React from 'react';
import { useChatStore } from '@/store/chatStore';

export const ChatHeader: React.FC = () => {
  const { closeChat, minimizeChat, isMinimized, clearChat } = useChatStore();

  return (
    <div className="
      flex items-center justify-between
      px-4 py-3
      bg-gradient-to-r from-blue-600 to-blue-700
      text-white
      rounded-t-2xl
      border-b border-blue-500
    ">
      {/* Left: Avatar and Title */}
      <div className="flex items-center gap-3">
        {/* Chess Coach Avatar */}
        <div className="
          w-10 h-10 rounded-full
          bg-white/20 backdrop-blur-sm
          flex items-center justify-center
          border-2 border-white/30
        ">
          <svg 
            className="w-6 h-6" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={2} 
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" 
            />
          </svg>
        </div>

        {/* Title and Status */}
        <div>
          <h3 className="font-semibold text-base">Chess Coach</h3>
          <div className="flex items-center gap-1.5 text-xs text-blue-100">
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            <span>Online</span>
          </div>
        </div>
      </div>

      {/* Right: Action Buttons */}
      <div className="flex items-center gap-1">
        {/* Clear Chat Button */}
        <button
          onClick={() => {
            if (confirm('Clear chat history?')) {
              clearChat();
            }
          }}
          className="
            p-2 rounded-lg
            hover:bg-white/10
            transition-colors
          "
          aria-label="Clear chat"
          title="Clear chat"
        >
          <svg 
            className="w-5 h-5" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={2} 
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" 
            />
          </svg>
        </button>

        {/* Minimize Button */}
        <button
          onClick={minimizeChat}
          className="
            p-2 rounded-lg
            hover:bg-white/10
            transition-colors
          "
          aria-label="Minimize chat"
          title="Minimize"
        >
          <svg 
            className="w-5 h-5" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={2} 
              d="M20 12H4" 
            />
          </svg>
        </button>

        {/* Close Button */}
        <button
          onClick={closeChat}
          className="
            p-2 rounded-lg
            hover:bg-white/10 hover:bg-red-500/20
            transition-colors
          "
          aria-label="Close chat"
          title="Close"
        >
          <svg 
            className="w-5 h-5" 
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
    </div>
  );
};

export default ChatHeader;
