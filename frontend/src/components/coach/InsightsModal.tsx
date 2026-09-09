import { useCallback, useEffect, useState } from 'react';
import { Brain, Loader2, X } from 'lucide-react';
import { memoryApi, type MemoryItem } from '@/lib/api';

type MemoryFilter = 'all' | 'pattern' | 'coaching';

const FILTERS: Array<{ id: MemoryFilter; label: string; contentType?: string }> = [
  { id: 'all', label: 'Everything' },
  { id: 'pattern', label: 'From Your Games', contentType: 'pattern' },
  { id: 'coaching', label: 'From Our Chats', contentType: 'coaching' },
];

function relativeDate(value: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function InsightsModal({
  userId,
  onClose,
}: {
  userId: number;
  onClose: () => void;
}) {
  const [filter, setFilter] = useState<MemoryFilter>('all');
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const selected = FILTERS.find((entry) => entry.id === filter);
      const response = await memoryApi.list(userId, {
        contentType: selected?.contentType,
        limit: 50,
      });
      setMemories(response.memories);
      setTotalCount(response.total_count);
    } catch {
      setError('Could not load what your coach knows. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [filter, userId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end bg-black/70 p-0 backdrop-blur-sm sm:items-center sm:justify-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label="What your coach knows"
    >
      <div className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-t-2xl border border-[#3c4a42] bg-[#201f1f] p-6 shadow-2xl sm:rounded-xl">
        <div className="mb-6 flex items-start justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-wider text-brand-primary">
              Insights
            </p>
            <h2 className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <Brain className="h-6 w-6 text-brand-primary" /> What Your Coach Knows
            </h2>
            <p className="mt-2 text-sm leading-6 text-[#bbcabf]">
              Everything your coach has picked up from your conversations and analyzed games —
              the same facts your coach reasons from.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="p-1 text-[#bbcabf] hover:text-[#e5e2e1]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="mb-4 flex flex-wrap gap-2">
          {FILTERS.map((entry) => (
            <button
              key={entry.id}
              type="button"
              onClick={() => setFilter(entry.id)}
              className={`rounded-full border px-4 py-1.5 font-mono text-xs transition-colors ${
                filter === entry.id
                  ? 'border-brand-primary bg-brand-primary/10 text-brand-primary'
                  : 'border-[#3c4a42] text-[#bbcabf] hover:border-brand-primary hover:text-brand-primary'
              }`}
            >
              {entry.label}
            </button>
          ))}
          {!loading && !error && (
            <span className="ml-auto self-center font-mono text-xs text-[#bbcabf]">
              {totalCount} {totalCount === 1 ? 'memory' : 'memories'}
            </span>
          )}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          {loading ? (
            <div className="flex items-center justify-center py-10 text-sm text-[#bbcabf]">
              <Loader2 className="mr-2 h-4 w-4 animate-spin text-brand-primary" /> Loading your
              coach&apos;s memory...
            </div>
          ) : error ? (
            <p className="py-6 text-center text-sm text-brand-error">{error}</p>
          ) : memories.length === 0 ? (
            <p className="py-10 text-center text-sm leading-6 text-[#bbcabf]">
              Your coach has no saved notes here yet. Chat with your coach and analyze games —
              everything it learns is kept here so you always stay in control of what it knows.
            </p>
          ) : (
            <ul className="space-y-3">
              {memories.map((memory) => (
                <li
                  key={memory.id}
                  className="rounded-lg border border-[#262626] bg-[#171717] px-4 py-3"
                >
                  <p className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wide text-[#bbcabf]">
                    {memory.content_type === 'pattern' ? 'From your games' : 'From our chats'}
                    {relativeDate(memory.updated_at) && (
                      <span className="ml-auto normal-case tracking-normal">{relativeDate(memory.updated_at)}</span>
                    )}
                  </p>
                  <p className="mt-1.5 text-sm leading-6 text-[#e5e2e1]">{memory.content_text}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
