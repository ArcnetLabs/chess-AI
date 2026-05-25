/**
 * Message List Component
 * Scrollable container for chat messages
 */

import React, { useEffect, useRef } from 'react';
import { useChatStore } from '@/store/chatStore';
import { Message } from './Message';
import { TypingIndicator } from './TypingIndicator';

export const MessageList: React.FC = () => {
  const { messages, isTyping, sendMessage } = useChatStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleSuggestionClick = (suggestion: string) => {
    sendMessage(suggestion);
  };

  return (
    <div
      ref={containerRef}
      className="
        flex-1 overflow-y-auto
        bg-white
        scroll-smooth
      "
      style={{ maxHeight: 'calc(600px - 140px)' }}
    >
      {/* Messages */}
      {messages.length === 0 ? (
        <div className="flex items-center justify-center h-full p-8 text-center">
          <div className="text-gray-500">
            <svg 
              className="w-16 h-16 mx-auto mb-4 text-gray-300" 
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
            <p className="text-sm">No messages yet</p>
            <p className="text-xs mt-1">Start a conversation with your chess coach!</p>
          </div>
        </div>
      ) : (
        <div className="py-4 space-y-2">
          {messages.map((message) => (
            <Message
              key={message.id}
              message={message}
              onSuggestionClick={handleSuggestionClick}
            />
          ))}

          {/* Typing Indicator */}
          {isTyping && <TypingIndicator />}

          {/* Scroll anchor */}
          <div ref={messagesEndRef} />
        </div>
      )}
    </div>
  );
};

export default MessageList;
