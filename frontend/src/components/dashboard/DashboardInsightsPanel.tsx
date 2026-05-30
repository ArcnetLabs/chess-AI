import React from 'react';
import Link from 'next/link';
import { Brain, LineChart } from 'lucide-react';
import { Recommendation } from '@/types';

interface DashboardInsightsPanelProps {
  insights: Recommendation[];
}

function categoryTagClass(category: string): string {
  const c = category.toLowerCase();
  if (c.includes('opening')) return 'bg-brand-primary/10 text-brand-primary';
  if (c.includes('tactic') || c.includes('blunder')) return 'bg-brand-secondary/10 text-brand-secondary';
  return 'bg-[#fdfe6a]/10 text-[#fdfe6a]';
}

export const DashboardInsightsPanel: React.FC<DashboardInsightsPanelProps> = ({ insights }) => (
  <div className="relative overflow-hidden border-l-2 border-brand-primary/30 bg-surface-container p-6">
    <h3 className="mb-4 flex items-center gap-2 font-display text-lg font-bold uppercase tracking-tight text-content">
      <Brain className="h-5 w-5 text-brand-primary" strokeWidth={1.5} />
      AI Insights
    </h3>
    <div className="space-y-5">
      {insights.length > 0 ? (
        insights.slice(0, 3).map((insight, index) => (
          <div key={index} className="relative rounded-chess-md bg-surface-container-high p-4">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span
                className={`rounded-chess px-2 py-0.5 text-[8px] font-bold uppercase tracking-widest ${categoryTagClass(insight.category)}`}
              >
                {insight.category.replace(/_/g, ' ')}
              </span>
              {insight.priority && (
                <span className="text-[10px] text-content-muted capitalize">{insight.priority}</span>
              )}
            </div>
            <p className="text-sm leading-relaxed text-content-muted">{insight.description}</p>
            {(insight.improvement || insight.title) && (
              <p className="mt-2 text-xs text-content">{insight.improvement ?? insight.title}</p>
            )}
          </div>
        ))
      ) : (
        <div className="rounded-chess-md bg-surface-container-high p-4">
          <p className="text-sm leading-relaxed text-content-muted">
            Sync and analyze games to unlock personalized coaching insights from your patterns and
            engine data.
          </p>
        </div>
      )}
    </div>
    <Link
      href="/coach"
      className="mt-6 flex w-full items-center justify-center border border-brand-primary/20 py-3 text-[10px] font-bold uppercase tracking-[0.2em] text-content transition-all hover:bg-brand-primary hover:text-brand-on-primary"
    >
      Full cognitive review
    </Link>
    <LineChart
      className="pointer-events-none absolute right-4 top-4 h-16 w-16 text-brand-primary opacity-5"
      aria-hidden
    />
  </div>
);
