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
  const getPriorityStyles = () => {
    switch (priority) {
      case 'high':
        return 'bg-brand-error/10 text-brand-error';
      case 'medium':
        return 'bg-brand-primary/10 text-brand-primary';
      case 'low':
        return 'bg-brand-secondary/10 text-brand-secondary';
    }
  };

  const getPriorityIcon = () => {
    switch (priority) {
      case 'high':
        return <AlertCircle className="h-5 w-5" />;
      case 'medium':
        return <Target className="h-5 w-5" />;
      case 'low':
        return <CheckCircle2 className="h-5 w-5" />;
    }
  };

  return (
    <div className={`rounded-chess-md p-4 ${getPriorityStyles()}`}>
      <div className="flex items-start gap-3">
        {getPriorityIcon()}
        <div className="flex-1">
          <h4 className="font-semibold capitalize text-content">
            {category.replace('_', ' ')}
          </h4>
          <p className="mt-1 text-sm text-content-muted">{description}</p>
          <p className="mt-2 text-xs font-medium text-content">{improvement}</p>
        </div>
        <span className="rounded bg-surface-bright/80 px-2 py-1 text-xs font-medium uppercase tracking-wide text-content-muted">
          {priority}
        </span>
      </div>
    </div>
  );
};
