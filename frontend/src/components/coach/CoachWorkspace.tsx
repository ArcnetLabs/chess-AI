import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ArrowUp,
  ChevronDown,
  Clipboard,
  Mic,
  Plus,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Loader2,
} from 'lucide-react';
import toast from 'react-hot-toast';
import api from '@/lib/api';
import { KnightGlyph } from '@/components/brand/ChessRunMark';
import { AnalysisModal } from './AnalysisModal';
import { useAnalysisStatus, useChatSession, useCurrentUser } from '@/hooks';
import { useChatStore } from '@/store/chatStore';
import type { AnalysisRange } from './chatMode';

const STARTERS = [
  { title: 'Pattern Recognition', prompt: 'What patterns do you see in my games?' },
  { title: 'Conversion Issues', prompt: 'Why do I lose winning positions?' },
  { title: 'Rating Goals', prompt: "What's holding me back from 1800?" },
  { title: 'Opening Prep', prompt: 'Which openings fit my playing style?' },
];

const INTERVIEW_STARTERS = [
  { title: 'Full Baseline', prompt: 'Interview me about my rating goal, my weakest area, my weekly time budget, and my openings.' },
  { title: 'Your Goal', prompt: 'My rating goal is to reach ' },
  { title: 'Time Budget', prompt: 'I can train around ' },
  { title: 'Openings Repertoire', prompt: 'As White I play ' },
];

const ANALYZE_STARTERS = [
  { title: 'Evaluate A Position', prompt: 'Evaluate this position for me: ' },
  { title: 'Best Plan Here', prompt: 'What is the best plan for this position? ' },
  { title: 'Did I Blunder', prompt: 'Did I blunder in this position? ' },
  { title: 'Understand The Idea', prompt: 'Explain the key idea in this position: ' },
];

export function CoachWorkspace() {
  const { user, loading } = useCurrentUser();
  const { watchJob, isTracking, error: analysisError } = useAnalysisStatus(user?.id);
  const sendMessage = useChatStore((state) => state.sendMessage);
  const messages = useChatStore((state) => state.messages);
  const isTyping = useChatStore((state) => state.isTyping);
  const error = useChatStore((state) => state.error);
  const sessionMode = useChatStore((state) => state.sessionMode);
  const isRestoringSession = useChatStore((state) => state.isRestoringSession);
  const hasUserMessage = messages.some((message) => message.role === 'user');
  const [input, setInput] = useState('');
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [selectedRange, setSelectedRange] = useState<AnalysisRange>(30);
  const [customDays, setCustomDays] = useState(14);
  const [startingAnalysis, setStartingAnalysis] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [showScrollChip, setShowScrollChip] = useState(false);

  useChatSession(user?.id);

  const visibleMessages = useMemo(
    () => messages.filter((message) => message.role !== 'system'),
    [messages],
  );

  const starters =
    sessionMode === 'interview' ? INTERVIEW_STARTERS
      : sessionMode === 'analyze' ? ANALYZE_STARTERS
        : STARTERS;
  const composerPlaceholder =
    sessionMode === 'interview' ? "Answer your coach's question..."
      : sessionMode === 'analyze' ? 'Paste a FEN or describe the position...'
        : 'What are we working on today?';

  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [visibleMessages.length, isTyping]);

  const handleSend = (e: FormEvent) => {
    e.preventDefault();
    const content = input.trim();
    if (!content || isTyping) return;
    setInput('');
    void sendMessage(content);
  };

  function daysForRange(range: AnalysisRange, custom: number): number | undefined {
    if (range === 'all') return undefined;
    if (range === 'month') return new Date().getDate();
    return range === 'custom' ? custom : range;
  }

  const handleStartAnalysis = async () => {
    if (!user) return;
    setStartingAnalysis(true);
    try {
      await api.games.fetchRecent(user.id, {
        days: daysForRange(selectedRange, customDays),
      });
      const response = await api.analysis.analyzeGames(user.id, {
        days: daysForRange(selectedRange, customDays),
      });
      if (
        response &&
        typeof response === 'object' &&
        'status' in response &&
        (response as { status?: string }).status === 'queued' &&
        (response as { job_id?: string }).job_id
      ) {
        watchJob((response as { job_id: string }).job_id, {
          onComplete: () => toast.success('Analysis complete'),
          onError: () => toast.error('Analysis failed'),
        });
      }
      setAnalysisOpen(false);
    } catch (err) {
      console.error(err);
    } finally {
      setStartingAnalysis(false);
    }
  };

  if (isRestoringSession && visibleMessages.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface text-content-muted">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Setting things
        up...
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen flex-col bg-surface">
      {/* thread scroll area */}
      <div
        ref={scrollRef}
        onScroll={(event) => {
          const el = event.currentTarget;
          const gap = el.scrollHeight - el.scrollTop - el.clientHeight;
          setShowScrollChip(gap > 160);
        }}
        className="flex-1 overflow-y-auto px-4 pb-4 pt-8 sm:px-8"
      >
        <div className="mx-auto w-full max-w-[760px] space-y-7 pb-40">
          {visibleMessages.length === 0 ? (
            <div className="flex flex-col items-center pt-[16vh] text-center">
              <KnightGlyph className="mb-6 h-16 w-16 text-brand-primary" />
              <h1 className="text-2xl font-bold tracking-tight text-content sm:text-[28px]">
                Ask ChessRun
              </h1>
              <p className="mt-2 text-[15px] text-content-muted">
                Your AI Chess Advisor — grounded in every game you&apos;ve played.
              </p>
              <div className="mt-8 flex max-w-[560px] flex-wrap justify-center gap-2.5">
                {starters.map((starter) => (
                  <button
                    key={starter.title}
                    type="button"
                    onClick={() => setInput(starter.prompt)}
                    className="rounded-xl border border-surface-bright/40 bg-surface-container/60 px-4 py-2.5 text-sm text-content transition-colors hover:border-brand-primary/40 hover:bg-surface-bright/30"
                  >
                    {starter.title}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            visibleMessages.map((message) =>
              message.role === 'user' ? (
                <div key={message.id} className="flex justify-end">
                  <div className="max-w-[85%] rounded-[22px] rounded-br-lg bg-surface-container-high px-5 py-3.5 text-[15px] leading-7 text-content">
                    {message.content}
                  </div>
                </div>
              ) : (
                <div key={message.id} className="group flex flex-col">
                  <div className="max-w-none text-[15px] leading-7 text-content [&_a]:underline [&_li]:mt-1 [&_strong]:font-semibold">
                    <ReactMarkdown remarkPlugins={[remarkGfm] as never}>{message.content}</ReactMarkdown>
                  </div>
                  {/* assistant action row (12906): copy / like / dislike */}
                  <div className="mt-2 flex items-center gap-3 text-content-muted opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
                    <button
                      type="button"
                      onClick={() => {
                        void navigator.clipboard.writeText(message.content);
                        toast.success('Copied');
                      }}
                      className="rounded-md p-1 transition-colors hover:bg-surface-bright/25 hover:text-content focus:opacity-100"
                      aria-label="Copy reply"
                    >
                      <Clipboard className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => toast.success('Thanks — noted')}
                      className="rounded-md p-1 transition-colors hover:bg-surface-bright/25 hover:text-content"
                      aria-label="Good reply"
                    >
                      <ThumbsUp className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => toast('Sorry — tell me what was off and I will adjust')}
                      className="rounded-md p-1 transition-colors hover:bg-surface-bright/25 hover:text-content"
                      aria-label="Bad reply"
                    >
                      <ThumbsDown className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ),
            )
          )}
          {isTyping && (
            <div className="flex items-center gap-2.5 text-[15px] text-content-muted">
              <Sparkles className="h-4 w-4 text-brand-primary" />
              <span>Setting things up...</span>
            </div>
          )}
          {error ? <p className="text-sm text-brand-error">{String(error)}</p> : null}
          {analysisError ? <p className="text-sm text-brand-error">{String(analysisError)}</p> : null}
        </div>
      </div>

      {/* floating scroll-to-bottom chip */}
      {showScrollChip && (
        <button
          type="button"
          aria-label="Scroll to bottom"
          onClick={() => {
            const node = scrollRef.current;
            if (node) node.scrollTop = node.scrollHeight;
          }}
          className="absolute bottom-[150px] left-1/2 z-10 flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-full border border-surface-bright/60 bg-surface-container text-content shadow-xl"
        >
          <ChevronDown className="h-4 w-4" />
        </button>
      )}

      {/* composer */}
      <div className="pointer-events-none sticky bottom-0 z-10 bg-gradient-to-t from-surface via-surface/95 to-transparent pb-5 pt-6">
        <form
          onSubmit={handleSend}
          className="pointer-events-auto mx-auto w-full max-w-[720px] px-4 sm:px-0"
        >
          <div className="flex items-center gap-2.5 rounded-full border border-surface-bright/40 bg-surface-container py-2.5 pl-3 pr-2.5 shadow-brand-ambient">
            <button
              type="button"
              aria-label="Attach a game"
              onClick={() => setAnalysisOpen(true)}
              disabled={isTracking}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-bright/30 text-content-muted transition-colors hover:bg-surface-bright/50 hover:text-content disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
            </button>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={composerPlaceholder}
              className="min-w-0 flex-1 bg-transparent py-2 text-[15px] leading-6 text-content outline-none placeholder:text-content-muted/60"
            />
            <button
              type="button"
              aria-label="Dictate message"
              onClick={() => toast('Dictation is coming soon')}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-bright/30 text-content-muted transition-colors hover:bg-surface-bright/50 hover:text-content"
            >
              <Mic className="h-4 w-4" />
            </button>
            <button
              type="submit"
              disabled={!input.trim() || isTyping}
              aria-label="Send"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-primary text-brand-on-primary shadow-brand-glow transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-25 disabled:shadow-none"
            >
              <ArrowUp className="h-4 w-4" />
            </button>
          </div>
          <p className="mt-2.5 text-center text-xs text-content-muted/50">
            ChessRun can make mistakes — every claim is grounded in your analyzed games.
          </p>
        </form>
      </div>

      {analysisOpen && (
        <AnalysisModal
          range={selectedRange}
          customDays={customDays}
          starting={startingAnalysis}
          onSelect={setSelectedRange}
          onCustomDays={setCustomDays}
          onClose={() => !startingAnalysis && setAnalysisOpen(false)}
          onStart={() => void handleStartAnalysis()}
        />
      )}
    </div>
  );
}
