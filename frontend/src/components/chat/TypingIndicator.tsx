/**
 * Typing Indicator Component
 * Animated dots showing coach is typing
 */

import React from 'react';

export const TypingIndicator: React.FC = () => {
  return (
    <div className="flex items-start gap-2 px-4 py-2">
      {/* Avatar */}
      <div className="
        w-8 h-8 rounded-full
        bg-blue-100 flex-shrink-0
        flex items-center justify-center
      ">
        <svg 
          className="w-5 h-5 text-blue-600" 
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

      {/* Typing Bubble */}
      <div className="
        bg-gray-100 rounded-2xl rounded-tl-sm
        px-4 py-3
        flex items-center gap-1
      ">
        <div className="flex gap-1">
          <div className="
            w-2 h-2 rounded-full bg-gray-400
            animate-bounce
          " style={{ animationDelay: '0ms' }} />
          <div className="
            w-2 h-2 rounded-full bg-gray-400
            animate-bounce
          " style={{ animationDelay: '150ms' }} />
          <div className="
            w-2 h-2 rounded-full bg-gray-400
            animate-bounce
          " style={{ animationDelay: '300ms' }} />
        </div>
        <span className="text-sm text-gray-500 ml-2">Typing...</span>
      </div>
    </div>
  );
};

export default TypingIndicator;
