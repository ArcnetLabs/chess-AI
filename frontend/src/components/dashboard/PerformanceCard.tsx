import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface PerformanceCardProps {
  title: string;
  value: string | number;
  change?: number;
  icon: React.ReactNode;
  trend?: 'up' | 'down' | 'stable';
  subtitle?: string;
}

export const PerformanceCard: React.FC<PerformanceCardProps> = ({
  title,
  value,
  change,
  icon,
  trend,
  subtitle,
}) => {
  const getTrendIcon = () => {
    if (trend === 'up') return <TrendingUp className="h-4 w-4 text-brand-secondary" />;
    if (trend === 'down') return <TrendingDown className="h-4 w-4 text-brand-error" />;
    return null;
  };

  return (
    <div className="chessrun-card">
      <div className="flex items-center justify-between">
        <div>
          <p className="chessrun-label">{title}</p>
          <p className="font-display text-2xl font-bold text-content">{value}</p>
          {subtitle && <p className="mt-1 text-xs text-content-muted">{subtitle}</p>}
          {change !== undefined && (
            <div className="mt-2 flex items-center">
              {getTrendIcon()}
              <span
                className={`ml-1 text-sm ${
                  trend === 'up'
                    ? 'text-brand-secondary'
                    : trend === 'down'
                      ? 'text-brand-error'
                      : 'text-content-muted'
                }`}
              >
                {change > 0 ? '+' : ''}
                {change} from last week
              </span>
            </div>
          )}
        </div>
        <div className="text-brand-primary">{icon}</div>
      </div>
    </div>
  );
};
