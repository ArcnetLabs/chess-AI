/**
 * Message Component
 * Individual chat message (user or assistant)
 */

import React from 'react';
import { Message as MessageType } from '@/types/chat.types';
import { AnalysisCard } from './AnalysisCard';
import { SuggestionChips } from './SuggestionChips';

interface MessageProps {
  message: MessageType;
  onSuggestionClick?: (suggestion: string) => void;
}

export const Message: React.FC<MessageProps> = ({ message, onSuggestionClick }) => {
  const isUser = message.role === 'user';
  const hasAnalysis = message.metadata?.analysis;
  const hasSuggestions = message.metadata?.suggestions && message.metadata.suggestions.length > 0;

  const formatTime = (date: Date): string => {
    return new Date(date).toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  return (
    <div className={`flex items-start gap-2 px-4 py-2 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar (only for assistant) */}
      {!isUser && (
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
      )}

      {/* Message Content */}
      <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-[80%]`}>
        {/* Message Bubble */}
        <div className={`
          rounded-2xl px-4 py-2.5
          ${isUser 
            ? 'bg-blue-600 text-white rounded-tr-sm' 
            : 'bg-gray-100 text-gray-800 rounded-tl-sm'
          }
        `}>
          {/* Message Text */}
          <div className="text-sm whitespace-pre-wrap break-words">
            {message.content}
          </div>

          {/* Analysis Card (if present) */}
          {hasAnalysis && message.metadata?.analysis && (
            <AnalysisCard analysis={message.metadata.analysis} />
          )}
        </div>

        {/* Suggestions (if present) */}
        {hasSuggestions && onSuggestionClick && message.metadata?.suggestions && (
          <div className="mt-2 w-full">
            <SuggestionChips
              suggestions={message.metadata.suggestions}
              onSelect={onSuggestionClick}
            />
          </div>
        )}

        {/* Timestamp */}
        <div className={`
          text-xs text-gray-500 mt-1 px-1
          ${isUser ? 'text-right' : 'text-left'}
        `}>
          {formatTime(message.timestamp)}
        </div>
      </div>
    </div>
  );
};

export default Message;
