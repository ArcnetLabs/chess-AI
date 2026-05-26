import React from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import { MoveQualityStats } from '@/types';

const MOVE_QUALITY_COLORS: Record<string, string> = {
  Brilliant: '#10b981',
  Great: '#22c55e',
  Best: '#84cc16',
  Excellent: '#eab308',
  Good: '#f59e0b',
  Inaccuracy: '#f97316',
  Mistake: '#ef4444',
  Blunder: '#dc2626',
};

export function buildMoveQualityChartData(breakdown: MoveQualityStats) {
  return [
    { name: 'Brilliant', value: breakdown.brilliant_moves },
    { name: 'Great', value: breakdown.great_moves },
    { name: 'Best', value: breakdown.best_moves },
    { name: 'Excellent', value: breakdown.excellent_moves },
    { name: 'Good', value: breakdown.good_moves },
    { name: 'Inaccuracy', value: breakdown.inaccuracies },
    { name: 'Mistake', value: breakdown.mistakes },
    { name: 'Blunder', value: breakdown.blunders },
  ]
    .filter((item) => item.value > 0)
    .map((item) => ({ ...item, fill: MOVE_QUALITY_COLORS[item.name] }));
}

interface MoveQualityChartProps {
  breakdown: MoveQualityStats;
  title?: string;
}

export const MoveQualityChart: React.FC<MoveQualityChartProps> = ({
  breakdown,
  title = 'Move Quality Distribution',
}) => {
  const chartData = buildMoveQualityChartData(breakdown);

  return (
    <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
      <h3 className="text-lg font-semibold mb-4 text-white">{title}</h3>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            outerRadius={100}
            fill="#8884d8"
            dataKey="value"
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.fill} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: '#374151',
              border: 'none',
              borderRadius: '8px',
              color: '#fff',
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};
