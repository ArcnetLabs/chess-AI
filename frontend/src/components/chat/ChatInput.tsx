/**
 * Chat Input Component
 * Text input with send button
 */

import React, { useState, useRef, KeyboardEvent } from 'react';
import { useChatStore } from '@/store/chatStore';

export const ChatInput: React.FC = () => {
  const { sendMessage, isTyping, currentPosition } = useChatStore();
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = async () => {
    if (!input.trim() || isTyping) return;

    const message = input.trim();
    setInput('');
    
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    await sendMessage(message, currentPosition || undefined);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Send on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    
    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  };

  return (
    <div className="
      px-4 py-3
      bg-white
      border-t border-gray-200
      rounded-b-2xl
    ">
      <div className="flex items-end gap-2">
        {/* Text Input */}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder="Type your message..."
          disabled={isTyping}
          rows={1}
          className="
            flex-1 resize-none
            px-4 py-2.5
            bg-gray-50
            border border-gray-200
            rounded-xl
            text-sm text-gray-800
            placeholder-gray-400
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-all
          "
          style={{ maxHeight: '120px' }}
        />

        {/* Send Button */}
        <button
          onClick={handleSend}
          disabled={!input.trim() || isTyping}
          className="
            flex-shrink-0
            w-10 h-10
            rounded-xl
            bg-blue-600 text-white
            hover:bg-blue-700
            active:bg-blue-800
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-all duration-150
            transform hover:scale-105 active:scale-95
            flex items-center justify-center
          "
          aria-label="Send message"
        >
          {isTyping ? (
            <svg 
              className="w-5 h-5 animate-spin" 
              fill="none" 
              viewBox="0 0 24 24"
            >
              <circle 
                className="opacity-25" 
                cx="12" 
                cy="12" 
                r="10" 
                stroke="currentColor" 
                strokeWidth="4"
              />
              <path 
                className="opacity-75" 
                fill="currentColor" 
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          ) : (
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
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" 
              />
            </svg>
          )}
        </button>
      </div>

      {/* Helper Text */}
      <div className="mt-2 text-xs text-gray-500 flex items-center justify-between">
        <span>Press Enter to send, Shift+Enter for new line</span>
        <span className={input.length > 450 ? 'text-orange-500' : ''}>
          {input.length}/500
        </span>
      </div>
    </div>
  );
};

export default ChatInput;
