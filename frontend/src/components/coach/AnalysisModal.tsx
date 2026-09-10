import { Loader2, X } from 'lucide-react';
import type { AnalysisRange } from './chatMode';

type RangeOption = { label: string; value: AnalysisRange };

export const RANGE_OPTIONS: RangeOption[] = [
  { label: '7 days', value: 7 },
  { label: '30 days', value: 30 },
  { label: 'All games', value: 'all' },
  { label: 'Custom', value: 'custom' },
];

export function AnalysisModal({
  range,
  customDays,
  starting,
  onSelect,
  onCustomDays,
  onClose,
  onStart,
}: {
  range: AnalysisRange;
  customDays: number;
  starting: boolean;
  onSelect: (value: AnalysisRange) => void;
  onCustomDays: (days: number) => void;
  onClose: () => void;
  onStart: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-md rounded-2xl border border-[#262626] bg-[#141414] p-6 shadow-2xl">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-brand-primary">Connect your games</h2>
            <p className="mt-1 text-sm leading-6 text-[#bbcabf]">
              Pull games from Chess.com and run the analysis pass so your coach has grounded
              facts to work from.
            </p>
          </div>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="rounded-md p-1 text-[#bbcabf] hover:bg-[#1f1f1f]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          {RANGE_OPTIONS.map((option) => (
            <button
              key={String(option.value)}
              type="button"
              onClick={() => onSelect(option.value)}
              className={`rounded-full px-4 py-1.5 text-sm transition-colors ${
                range === option.value
                  ? 'bg-brand-primary/15 text-brand-primary'
                  : 'bg-[#1c1c1c] text-[#bbcabf] hover:bg-[#242424]'
              }`}
            >
              {option.label}
            </button>
          ))}
          {range === 'custom' && (
            <label className="flex items-center gap-2 rounded-full px-3 text-sm text-[#bbcabf]">
              Days
              <input
                type="number"
                min={1}
                max={365}
                value={customDays}
                onChange={(e) => onCustomDays(Number(e.target.value) || 1)}
                className="w-16 rounded-md bg-[#1c1c1c] px-2 py-1 text-sm text-[#e5e2e1]"
              />
            </label>
          )}
        </div>

        <button
          type="button"
          onClick={onStart}
          disabled={starting}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-brand-primary px-4 py-3 font-medium text-[#0b351f] transition-opacity hover:opacity-90 disabled:opacity-60"
        >
          {starting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Fetching &amp; analyzing...
            </>
          ) : (
            'Run analysis'
          )}
        </button>
      </div>
    </div>
  );
}
