/**
 * Floating Chatbot Icon Component
 * Discord-style floating button in bottom-right corner
 */

import React from 'react';
import { useChatStore } from '@/store/chatStore';

export const ChatbotIcon: React.FC = () => {
  const { isOpen, unreadCount, toggleChat } = useChatStore();

  // Don't show icon when chat is open
  if (isOpen) {
    return null;
  }

  return (
    <button
      onClick={toggleChat}
      className="fixed bottom-24 right-6 z-50 group md:bottom-8"
      aria-label="Open chess coach chat"
    >
      {/* Main Icon Button */}
      <div className="relative">
        <div className={`
          w-16 h-16 rounded-2xl bg-brand-primary text-brand-on-primary
          flex items-center justify-center
          shadow-[0_8px_32px_rgba(132,255,0,0.3)] hover:shadow-brand-glow-lg
          transform transition-all duration-200
          hover:scale-105 active:scale-95
          ${unreadCount > 0 ? 'animate-pulse' : ''}
        `}>
          {/* Chess Knight Icon */}
          <svg 
            className="w-8 h-8" 
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

        {/* Notification Badge */}
        {unreadCount > 0 && (
          <div className="
            absolute -top-1 -right-1
            w-6 h-6 rounded-full
            bg-red-500 text-white
            flex items-center justify-center
            text-xs font-bold
            border-2 border-white
            animate-bounce
          ">
            {unreadCount > 9 ? '9+' : unreadCount}
          </div>
        )}

        {/* Pulse Ring Animation */}
        {unreadCount > 0 && (
          <div className="
            absolute inset-0 rounded-full
            bg-blue-400 opacity-75
            animate-ping
          " />
        )}
      </div>

      {/* Tooltip */}
      <div className="
        absolute bottom-full right-0 mb-2
        px-3 py-2 rounded-lg
        bg-gray-900 text-white text-sm
        whitespace-nowrap
        opacity-0 group-hover:opacity-100
        transition-opacity duration-200
        pointer-events-none
      ">
        Chat with Chess Coach
        <div className="
          absolute top-full right-4
          w-0 h-0
          border-l-4 border-l-transparent
          border-r-4 border-r-transparent
          border-t-4 border-t-gray-900
        " />
      </div>
    </button>
  );
};

export default ChatbotIcon;
