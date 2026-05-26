import React from 'react';
import { Trophy, Target, Brain, Zap } from 'lucide-react';
import { PerformanceCard } from './PerformanceCard';

interface AnalysisSummary {
  total_games_analyzed: number;
  accuracy_percentage?: number;
  average_acpl?: number;
  most_played_openings?: [string, number][];
}

interface PerformanceOverviewProps {
  analysisSummary: AnalysisSummary;
}

export const PerformanceOverview: React.FC<PerformanceOverviewProps> = ({ analysisSummary }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
    <PerformanceCard
      title="Games Analyzed"
      value={analysisSummary.total_games_analyzed}
      icon={<Trophy className="w-6 h-6" />}
      subtitle="Last 7 days"
    />
    <PerformanceCard
      title="Average Accuracy"
      value={`${analysisSummary.accuracy_percentage?.toFixed(1) || 0}%`}
      icon={<Target className="w-6 h-6" />}
      subtitle="Higher is better"
    />
    <PerformanceCard
      title="ACPL"
      value={analysisSummary.average_acpl?.toFixed(0) || 'N/A'}
      icon={<Brain className="w-6 h-6" />}
      subtitle="Lower is better"
    />
    <PerformanceCard
      title="Favorite Opening"
      value={
        analysisSummary.most_played_openings?.[0]?.[0]
          ? analysisSummary.most_played_openings[0][0].length > 20
            ? `${analysisSummary.most_played_openings[0][0].substring(0, 20)}...`
            : analysisSummary.most_played_openings[0][0]
          : 'N/A'
      }
      icon={<Zap className="w-6 h-6" />}
      subtitle="Most played this week"
    />
  </div>
);
