/**
 * Suggestion Chips Component
 * Quick action buttons from backend suggestions
 */

import React from 'react';

interface SuggestionChipsProps {
  suggestions: string[];
  onSelect: (suggestion: string) => void;
  disabled?: boolean;
}

export const SuggestionChips: React.FC<SuggestionChipsProps> = ({
  suggestions,
  onSelect,
  disabled = false,
}) => {
  if (!suggestions || suggestions.length === 0) {
    return null;
  }

  return (
    <div className="px-4 py-2">
      <div className="flex items-center gap-2 mb-2">
        <svg 
          className="w-4 h-4 text-gray-500" 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path 
            strokeLinecap="round" 
            strokeLinejoin="round" 
            strokeWidth={2} 
            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" 
          />
        </svg>
        <span className="text-xs font-medium text-gray-600">
          Suggestions:
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            onClick={() => onSelect(suggestion)}
            disabled={disabled}
            className="
              px-3 py-1.5 rounded-full
              bg-blue-50 text-blue-700
              text-sm font-medium
              border border-blue-200
              hover:bg-blue-100 hover:border-blue-300
              active:bg-blue-200
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-all duration-150
              transform hover:scale-105 active:scale-95
            "
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
};

export default SuggestionChips;
