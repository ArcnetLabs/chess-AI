import React from 'react';
import Link from 'next/link';

interface PhasePerformance {
  opening_acpl?: number;
  middlegame_acpl?: number;
  endgame_acpl?: number;
}

interface DashboardTrainingProgressProps {
  phasePerformance?: PhasePerformance;
  hasData: boolean;
}

function acplToProgress(acpl: number | undefined): number {
  if (acpl == null || Number.isNaN(acpl)) return 0;
  return Math.max(0, Math.min(100, Math.round(100 - acpl * 4)));
}

export const DashboardTrainingProgress: React.FC<DashboardTrainingProgressProps> = ({
  phasePerformance,
  hasData,
}) => {
  const opening = acplToProgress(phasePerformance?.opening_acpl);
  const middlegame = acplToProgress(phasePerformance?.middlegame_acpl);
  const endgame = acplToProgress(phasePerformance?.endgame_acpl);

  const rows = hasData
    ? [
        { label: 'Opening precision', value: opening, color: 'bg-brand-primary' },
        { label: 'Middlegame', value: middlegame, color: 'bg-brand-secondary' },
        { label: 'Endgame mastery', value: endgame, color: 'bg-brand-primary' },
      ]
    : [
        { label: 'Pattern recognition', value: 0, color: 'bg-brand-secondary' },
        { label: 'Endgame mastery', value: 0, color: 'bg-brand-primary' },
      ];

  return (
    <div className="bg-surface-low p-6">
      <p className="chessrun-label mb-4">Training progress</p>
      <div className="space-y-4">
        {rows.map((row) => (
          <div key={row.label}>
            <div className="flex items-end justify-between">
              <span className="text-xs font-bold text-content">{row.label}</span>
              <span className="text-xs text-brand-primary">
                {hasData ? `${row.value}%` : '—'}
              </span>
            </div>
            <div className="mt-2 h-1 rounded-full bg-surface-container">
              <div
                className={`h-full rounded-full shadow-[0_0_8px_rgba(132,255,0,0.4)] ${row.color}`}
                style={{ width: `${row.value}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      <Link
        href="/training"
        className="mt-4 inline-block text-[10px] font-bold uppercase tracking-widest text-brand-primary hover:underline"
      >
        Open training →
      </Link>
    </div>
  );
};
