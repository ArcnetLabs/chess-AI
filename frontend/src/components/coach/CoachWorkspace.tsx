import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ArrowUp,
  Copy,
  Loader2,
  Plus,
} from 'lucide-react';
import toast from 'react-hot-toast';
import api from '@/lib/api';
import { KnightGlyph } from '@/components/brand/ChessRunMark';
import { AnalysisModal } from './AnalysisModal';
import { useAnalysisStatus, useChatSession, useCurrentUser, usePlayerProfile } from '@/hooks';
import { useChatStore } from '@/store/chatStore';
import type { AnalysisRange, ChatMode } from './chatMode';

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

function ChatMessage({ role, content }: { role: 'user' | 'assistant'; content: string }) {
  if (role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-3xl bg-[#262626] px-5 py-3 text-[15px] leading-7 text-[#e5e2e1]">
          {content}
        </div>
      </div>
    );
  }
  return (
    <div className="group flex flex-col">
      <div className="max-w-none text-[15px] leading-7 text-[#e5e2e1] [&_a]:text-brand-primary [&_a]:underline [&_li]:mt-1 [&_strong]:font-semibold">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
      <button
        type="button"
        onClick={() => {
          void navigator.clipboard.writeText(content);
          toast.success('Copied');
        }}
        className="mt-1.5 flex h-7 w-7 items-center justify-center rounded-md text-[#bbcabf] opacity-0 transition-opacity hover:bg-[#1c1c1c] hover:text-[#e5e2e1] focus:opacity-100 group-hover:opacity-100"
        aria-label="Copy reply"
      >
        <Copy className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function CoachWorkspace() {
  const { user, loading, refetchUser } = useCurrentUser();
  const { data: profile, refetch: refetchProfile } = usePlayerProfile(user?.id);
  const { watchJob, status, isTracking, error: analysisError } = useAnalysisStatus(user?.id);
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

  useChatSession(user?.id);

  useEffect(() => {
    if (status?.status !== 'completed' && status?.status !== 'partial') return;
    void refetchProfile();
    void refetchUser();
  }, [status?.status, refetchProfile, refetchUser]);

  const subtitle = useMemo(
    () =>
      sessionMode === 'interview'
        ? 'Start with a quick baseline interview.'
        : 'Your AI Chess Advisor',
    [sessionMode],
  );

  const sessionsStarters =
    sessionMode === 'interview' ? INTERVIEW_STARTERS
      : sessionMode === 'analyze' ? ANALYZE_STARTERS
        : STARTERS;
  const composerPlaceholder =
    sessionMode === 'interview' ? "Answer your coach's question..."
      : sessionMode === 'analyze' ? 'Paste a FEN or describe the position...'
        : 'What would you like to work on today?';

  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages.length, isTyping]);

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
      if (response.status === 'queued' && response.job_id) {
        watchJob(response.job_id, {
          onComplete: () => toast.success('Analysis complete'),
          onError: () => toast.error('Analysis failed'),
        });
      }
      setAnalysisOpen(false);
      void refetchUser();
    } catch (err) {
      console.error(err);
    } finally {
      setStartingAnalysis(false);
    }
  };

  if (isRestoringSession && messages.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0d0d0d] text-[#bbcabf]">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Restoring your
        conversation...
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen flex-col bg-[#0d0d0d] text-[#e5e2e1]">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-0 h-64 bg-gradient-to-b from-[#0f1411] to-transparent" />

      <div
        ref={scrollRef}
        className="relative z-10 flex flex-1 flex-col overflow-y-auto px-4 pb-6 pt-6 sm:px-6"
      >
        <div className="mx-auto w-full max-w-3xl space-y-8">
          {messages.length === 0 && (
            <div className="pt-[12vh] text-center">
              <KnightGlyph className="mx-auto mb-5 h-14 w-14 text-brand-primary" />
              <h1 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
                Ask ChessRun
              </h1>
              <p className="mt-3 text-base text-[#bbcabf]">{subtitle}</p>
              {sessionMode !== 'coach' && (
                <p className="mt-2 font-mono text-xs uppercase tracking-wider text-brand-primary">
                  {sessionMode === 'interview' ? 'Baseline interview' : 'Position analysis'}
                </p>
              )}
            </div>
          )}
          {messages.map((message) =>
            message.role === 'system' ? null : (
              <ChatMessage key={message.id} role={message.role} content={message.content} />
            ),
          )}
          {isTyping && (
            <div className="flex items-center gap-2 text-[15px] text-[#bbcabf]">
              <KnightGlyph className="h-5 w-5 text-brand-primary" />
              <span>Setting things up...</span>
            </div>
          )}
          {error && <p className="text-sm text-brand-error">{String(error)}</p>}
          {analysisError && <p className="text-sm text-brand-error">{String(analysisError)}</p>}
          {!hasUserMessage && (
            <div className="flex flex-wrap justify-center gap-2 pt-2">
              {sessionsStarters.map((starter) => (
                <button
                  key={starter.title}
                  type="button"
                  onClick={() => setInput(starter.prompt)}
                  className="rounded-full border border-[#262626] bg-[#141414] px-4 py-2 text-sm text-[#bbcabf] transition-colors hover:border-brand-primary/50 hover:text-[#e5e2e1]"
                >
                  {starter.title}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <form
        onSubmit={handleSend}
        className="sticky bottom-0 z-10 bg-gradient-to-t from-[#0d0d0d] via-[#0d0d0d] to-transparent px-4 pb-5 pt-2 sm:px-6"
      >
        <div className="mx-auto max-w-3xl">
          {!hasUserMessage && (
            <p className="hidden pb-2 text-center text-xs text-[#bbcabf]/50 sm:block">
              ChessRun can make mistakes — every claim is grounded in your analyzed games.
            </p>
          )}
          <div className="flex items-end gap-2 rounded-2xl border border-[#262626] bg-[#161616] px-3 py-2 shadow-xl">
            <button
              type="button"
              aria-label="Attach a game"
              onClick={() => setAnalysisOpen(true)}
              disabled={isTracking}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[#bbcabf] transition-colors hover:bg-[#242424] hover:text-[#e5e2e1] disabled:opacity-50"
            >
              <Plus className="h-5 w-5" />
            </button>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={composerPlaceholder}
              className="min-w-0 flex-1 bg-transparent py-2 text-[15px] leading-6 text-[#e5e2e1] outline-none placeholder:text-[#5d6a63]"
            />
            <button
              type="submit"
              disabled={!input.trim() || isTyping}
              aria-label="Send"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-primary text-[#0b351f] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-25"
            >
              <ArrowUp className="h-5 w-5" />
            </button>
          </div>
        </div>
      </form>

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
