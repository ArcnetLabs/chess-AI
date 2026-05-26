import React from 'react';
import { Brain } from 'lucide-react';
import { Recommendation } from '@/types';
import { CoachingInsightCard } from './CoachingInsightCard';

interface CoachingInsightsSectionProps {
  insights: Recommendation[];
}

export const CoachingInsightsSection: React.FC<CoachingInsightsSectionProps> = ({ insights }) => (
  <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 mb-8">
    <div className="flex items-center space-x-2 mb-6">
      <Brain className="w-6 h-6 text-blue-400" />
      <h3 className="text-xl font-semibold text-white">AI Coach Insights</h3>
    </div>
    <div className="space-y-4">
      {insights.length > 0 ? (
        insights.map((insight, index) => (
          <CoachingInsightCard
            key={index}
            category={insight.category}
            priority={insight.priority}
            description={insight.description}
            improvement={insight.improvement}
          />
        ))
      ) : (
        <div className="flex items-center justify-center py-12 text-gray-500">
          <div className="text-center">
            <Brain className="w-12 h-12 mx-auto mb-4 text-gray-600" />
            <p className="text-lg font-medium text-gray-400 mb-2">No insights available yet</p>
            <p className="text-sm text-gray-500 max-w-md mx-auto">
              Click <strong>&quot;Analyze with AI&quot;</strong> above to analyze your games and
              generate personalized coaching insights.
            </p>
          </div>
        </div>
      )}
    </div>
  </div>
);
