import React from 'react';
import { Brain } from 'lucide-react';
import { Recommendation } from '@/types';
import { CoachingInsightCard } from './CoachingInsightCard';

interface CoachingInsightsSectionProps {
  insights: Recommendation[];
}

function normalizePriority(
  priority: Recommendation['priority'],
): 'high' | 'medium' | 'low' {
  if (priority === 'high' || priority === 'medium' || priority === 'low') {
    return priority;
  }
  if (priority === 'critical') {
    return 'high';
  }
  return 'medium';
}

export const CoachingInsightsSection: React.FC<CoachingInsightsSectionProps> = ({
  insights,
}) => (
  <div className="chessrun-card mb-8">
    <div className="mb-6 flex items-center gap-2">
      <Brain className="h-6 w-6 text-brand-primary" />
      <h3 className="font-display text-xl font-semibold text-content">AI Coach Insights</h3>
    </div>
    <div className="space-y-4">
      {insights.length > 0 ? (
        insights.map((insight, index) => (
          <CoachingInsightCard
            key={index}
            category={insight.category}
            priority={normalizePriority(insight.priority)}
            description={insight.description}
            improvement={insight.improvement ?? insight.title ?? ''}
          />
        ))
      ) : (
        <div className="flex items-center justify-center py-12 text-content-muted">
          <div className="text-center">
            <Brain className="mx-auto mb-4 h-12 w-12 text-surface-bright" />
            <p className="mb-2 text-lg font-medium text-content-muted">
              No insights available yet
            </p>
            <p className="mx-auto max-w-md text-sm text-content-muted/80">
              Click <strong className="text-content">&quot;Analyze with AI&quot;</strong>{' '}
              above to analyze your games and generate personalized coaching insights.
            </p>
          </div>
        </div>
      )}
    </div>
  </div>
);
