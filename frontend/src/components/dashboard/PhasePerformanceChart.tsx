import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Trophy } from 'lucide-react';

interface PhasePerformance {
  opening_acpl?: number;
  middlegame_acpl?: number;
  endgame_acpl?: number;
}

interface PhasePerformanceChartProps {
  phasePerformance: PhasePerformance;
  onRefresh: () => void;
}

export const PhasePerformanceChart: React.FC<PhasePerformanceChartProps> = ({
  phasePerformance,
  onRefresh,
}) => {
  const chartData = [
    { phase: 'Opening', acpl: phasePerformance.opening_acpl || 0 },
    { phase: 'Middlegame', acpl: phasePerformance.middlegame_acpl || 0 },
    { phase: 'Endgame', acpl: phasePerformance.endgame_acpl || 0 },
  ];

  return (
    <div className="chessrun-card">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-display text-lg font-semibold text-content">
          Phase Performance (ACPL)
        </h3>
        <button
          type="button"
          onClick={onRefresh}
          className="flex items-center gap-1 text-xs text-brand-primary hover:text-brand-primary-dim"
          title="Refresh data"
        >
          Refresh
        </button>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f262e" />
          <XAxis dataKey="phase" stroke="#a7abb2" />
          <YAxis
            stroke="#a7abb2"
            label={{
              value: 'ACPL (Lower is better)',
              angle: -90,
              position: 'insideLeft',
              fill: '#a7abb2',
            }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#141a20',
              border: 'none',
              borderRadius: '4px',
              color: '#e7ebf3',
            }}
            formatter={(value: number) => [value.toFixed(1), 'ACPL']}
          />
          <Bar dataKey="acpl" fill="#84ff00" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export const ChartEmptyState: React.FC<{ message?: string }> = ({
  message = 'Analyze some games to see phase performance',
}) => (
  <div className="flex h-[300px] items-center justify-center text-content-muted">
    <div className="text-center">
      <Trophy className="mx-auto mb-4 h-12 w-12 text-surface-bright" />
      <p>{message}</p>
      <p className="mt-2 text-xs">Click &quot;Analyze&quot; on any game below</p>
    </div>
  </div>
);
