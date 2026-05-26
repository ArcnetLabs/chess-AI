import React from 'react';
import { AlertCircle, Target, CheckCircle2 } from 'lucide-react';

interface CoachingInsightCardProps {
  category: string;
  priority: 'high' | 'medium' | 'low';
  description: string;
  improvement: string;
}

export const CoachingInsightCard: React.FC<CoachingInsightCardProps> = ({
  category,
  priority,
  description,
  improvement,
}) => {
  const getPriorityColor = () => {
    switch (priority) {
      case 'high':
        return 'text-red-400 bg-red-900/20 border-red-800';
      case 'medium':
        return 'text-yellow-400 bg-yellow-900/20 border-yellow-800';
      case 'low':
        return 'text-green-400 bg-green-900/20 border-green-800';
    }
  };

  const getPriorityIcon = () => {
    switch (priority) {
      case 'high':
        return <AlertCircle className="w-5 h-5" />;
      case 'medium':
        return <Target className="w-5 h-5" />;
      case 'low':
        return <CheckCircle2 className="w-5 h-5" />;
    }
  };

  return (
    <div className={`p-4 rounded-lg border ${getPriorityColor()}`}>
      <div className="flex items-start space-x-3">
        {getPriorityIcon()}
        <div className="flex-1">
          <h4 className="font-semibold capitalize text-white">{category.replace('_', ' ')}</h4>
          <p className="text-sm mt-1 text-gray-300">{description}</p>
          <p className="text-xs mt-2 font-medium">💡 {improvement}</p>
        </div>
        <span
          className={`px-2 py-1 rounded text-xs font-medium ${
            priority === 'high'
              ? 'bg-red-800 text-red-200'
              : priority === 'medium'
                ? 'bg-yellow-800 text-yellow-200'
                : 'bg-green-800 text-green-200'
          }`}
        >
          {priority.toUpperCase()}
        </span>
      </div>
    </div>
  );
};
