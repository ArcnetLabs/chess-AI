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
    if (trend === 'up') return <TrendingUp className="w-4 h-4 text-green-400" />;
    if (trend === 'down') return <TrendingDown className="w-4 h-4 text-red-400" />;
    return null;
  };

  return (
    <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-400">{title}</p>
          <p className="text-2xl font-bold text-white">{value}</p>
          {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
          {change !== undefined && (
            <div className="flex items-center mt-2">
              {getTrendIcon()}
              <span
                className={`text-sm ml-1 ${
                  trend === 'up'
                    ? 'text-green-400'
                    : trend === 'down'
                      ? 'text-red-400'
                      : 'text-gray-400'
                }`}
              >
                {change > 0 ? '+' : ''}
                {change} from last week
              </span>
            </div>
          )}
        </div>
        <div className="text-blue-400">{icon}</div>
      </div>
    </div>
  );
};
