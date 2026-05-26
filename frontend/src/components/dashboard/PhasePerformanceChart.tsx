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
    <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Phase Performance (ACPL)</h3>
        <button
          onClick={onRefresh}
          className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
          title="Refresh data"
        >
          🔄 Refresh
        </button>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="phase" stroke="#9CA3AF" />
          <YAxis
            stroke="#9CA3AF"
            label={{
              value: 'ACPL (Lower is better)',
              angle: -90,
              position: 'insideLeft',
              fill: '#9CA3AF',
            }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1F2937',
              border: '1px solid #4B5563',
              borderRadius: '8px',
              color: '#fff',
            }}
            formatter={(value: number) => [value.toFixed(1), 'ACPL']}
          />
          <Bar dataKey="acpl" fill="#3b82f6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export const ChartEmptyState: React.FC<{ message?: string }> = ({
  message = 'Analyze some games to see phase performance',
}) => (
  <div className="flex items-center justify-center h-[300px] text-gray-500">
    <div className="text-center">
      <Trophy className="w-12 h-12 mx-auto mb-4 text-gray-600" />
      <p>{message}</p>
      <p className="text-xs mt-2">Click &quot;Analyze&quot; on any game below</p>
    </div>
  </div>
);
