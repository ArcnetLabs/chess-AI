/**
 * Analysis Card Component
 * Displays position analysis in a formatted card
 */

import React from 'react';
import { PositionAnalysis } from '@/types/chat.types';

interface AnalysisCardProps {
  analysis: PositionAnalysis;
}

export const AnalysisCard: React.FC<AnalysisCardProps> = ({ analysis }) => {
  const formatEvaluation = (evaluation: number): string => {
    if (evaluation > 3) return `Winning (+${evaluation.toFixed(2)})`;
    if (evaluation > 1) return `Clear advantage (+${evaluation.toFixed(2)})`;
    if (evaluation > 0.3) return `Slight edge (+${evaluation.toFixed(2)})`;
    if (evaluation > -0.3) return `Equal (${evaluation.toFixed(2)})`;
    if (evaluation > -1) return `Slightly worse (${evaluation.toFixed(2)})`;
    if (evaluation > -3) return `Difficult (${evaluation.toFixed(2)})`;
    return `Losing (${evaluation.toFixed(2)})`;
  };

  const getEvalColor = (evaluation: number): string => {
    if (evaluation > 1) return 'text-green-600';
    if (evaluation > 0.3) return 'text-green-500';
    if (evaluation > -0.3) return 'text-gray-600';
    if (evaluation > -1) return 'text-orange-500';
    return 'text-red-600';
  };

  return (
    <div className="
      mt-2 p-4 rounded-lg
      bg-gradient-to-br from-blue-50 to-indigo-50
      border border-blue-200
    ">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <svg 
          className="w-5 h-5 text-blue-600" 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path 
            strokeLinecap="round" 
            strokeLinejoin="round" 
            strokeWidth={2} 
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" 
          />
        </svg>
        <h4 className="font-semibold text-gray-800">Position Analysis</h4>
      </div>

      {/* Evaluation */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="bg-white/60 rounded-lg p-2">
          <div className="text-xs text-gray-600 mb-1">Evaluation</div>
          <div className={`text-sm font-bold ${getEvalColor(analysis.evaluation)}`}>
            {formatEvaluation(analysis.evaluation)}
          </div>
        </div>

        <div className="bg-white/60 rounded-lg p-2">
          <div className="text-xs text-gray-600 mb-1">Best Move</div>
          <div className="text-sm font-bold text-gray-800">
            {analysis.best_move}
          </div>
        </div>
      </div>

      {/* Phase and Material */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="bg-white/60 rounded-lg p-2">
          <div className="text-xs text-gray-600 mb-1">Phase</div>
          <div className="text-sm font-medium text-gray-700 capitalize">
            {analysis.phase}
          </div>
        </div>

        <div className="bg-white/60 rounded-lg p-2">
          <div className="text-xs text-gray-600 mb-1">Material</div>
          <div className={`text-sm font-medium ${
            analysis.material_balance > 0 ? 'text-green-600' :
            analysis.material_balance < 0 ? 'text-red-600' :
            'text-gray-600'
          }`}>
            {analysis.material_balance > 0 ? '+' : ''}{(analysis.material_balance / 100).toFixed(1)}
          </div>
        </div>
      </div>

      {/* Tactical Themes */}
      {analysis.tactical_themes && analysis.tactical_themes.length > 0 && (
        <div className="mb-3">
          <div className="text-xs text-gray-600 mb-2">Tactical Themes:</div>
          <div className="flex flex-wrap gap-1.5">
            {analysis.tactical_themes.slice(0, 4).map((theme, index) => (
              <span
                key={index}
                className="
                  px-2 py-1 rounded-md
                  bg-blue-100 text-blue-700
                  text-xs font-medium
                "
              >
                {theme.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Top Alternatives */}
      {analysis.candidate_moves && analysis.candidate_moves.length > 1 && (
        <div>
          <div className="text-xs text-gray-600 mb-2">Top Alternatives:</div>
          <div className="space-y-1">
            {analysis.candidate_moves.slice(0, 3).map((move, index) => (
              <div
                key={index}
                className="flex items-center justify-between text-sm bg-white/60 rounded px-2 py-1"
              >
                <span className="font-medium text-gray-700">
                  {index + 1}. {move.move}
                </span>
                <span className={`text-xs font-semibold ${getEvalColor(move.evaluation)}`}>
                  {move.evaluation > 0 ? '+' : ''}{move.evaluation.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisCard;
