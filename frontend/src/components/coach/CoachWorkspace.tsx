import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { AlertTriangle, BarChart3, Bot, CheckCircle2, ChevronDown, ChevronRight, Clock3, HelpCircle, Loader2, Menu, MessageSquarePlus, Paperclip, Send, Sparkles, X } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '@/lib/api';
import { useAnalysisStatus, useChatSession, useCurrentUser, usePlayerProfile } from '@/hooks';
import { useChatStore } from '@/store/chatStore';
import type { AnalysisJobStatus } from '@/types/analysis.types';

type AnalysisRange = 'all' | 7 | 30 | 'month' | 'custom';

const STARTERS = [
  { title: 'Pattern Recognition', prompt: 'What patterns do you see in my games?' },
  { title: 'Conversion Issues', prompt: 'Why do I lose winning positions?' },
  { title: 'Rating Goals', prompt: "What's holding me back from 1800?" },
  { title: 'Opening Prep', prompt: 'Which openings fit my playing style?' },
];

function firstProfileItem(items: unknown[] | null | undefined, fallback: string): string {
  const value = items?.[0];
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function friendlyBottleneck(items: unknown[] | null | undefined): string {
  const value = firstProfileItem(items, 'Analyze games to identify');
  if (/opening-phase acpl|high opening acpl/i.test(value)) return "Your openings are where we can make the quickest gains. Let's work on reaching the middlegame with a clearer plan.";
  if (/middlegame acpl|high middlegame acpl/i.test(value)) return "The middlegame is our best opportunity right now. Let's make your plans and calculations more consistent.";
  if (/endgame acpl|high endgame acpl/i.test(value)) return "Your endgames offer the clearest path forward. Let's sharpen the technique that turns close games into points.";
  return value;
}

function daysForRange(range: AnalysisRange, customDays: number): number | undefined {
  if (range === 'all') return undefined;
  if (range === 'month') return new Date().getDate();
  return range === 'custom' ? customDays : range;
}

export function CoachWorkspace() {
  const { user, loading, refetchUser } = useCurrentUser();
  const { data: profile, refetch: refetchProfile } = usePlayerProfile(user?.id);
  const { watchJob, cancelJob, status, isTracking, error: analysisError } = useAnalysisStatus(user?.id);
  const initializeSession = useChatStore((state) => state.initializeSession);
  const openSession = useChatStore((state) => state.openSession);
  const sessionId = useChatStore((state) => state.sessionId);
  const recentSessions = useChatStore((state) => state.recentSessions);
  const isRestoringSession = useChatStore((state) => state.isRestoringSession);
  const sendMessage = useChatStore((state) => state.sendMessage);
  const messages = useChatStore((state) => state.messages);
  const isTyping = useChatStore((state) => state.isTyping);
  const error = useChatStore((state) => state.error);
  const hasUserMessage = messages.some((message) => message.role === 'user');
  const [input, setInput] = useState('');
  const [profileOpen, setProfileOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [selectedRange, setSelectedRange] = useState<AnalysisRange>(30);
  const [customDays, setCustomDays] = useState(14);
  const [startingAnalysis, setStartingAnalysis] = useState(false);
  const [cancellingAnalysis, setCancellingAnalysis] = useState(false);

  useChatSession(user?.id);

  useEffect(() => {
    if (status?.status !== 'completed' && status?.status !== 'partial') return;
    void refetchProfile();
    void refetchUser();
  }, [status?.status, refetchProfile, refetchUser]);

  const profileData = useMemo(() => ({
    games: profile?.games_analyzed_count ?? user?.analyzed_games ?? 0,
    patterns: profile?.patterns_detected_count ?? 0,
    strength: firstProfileItem(profile?.primary_strengths, 'Building from your games'),
    bottleneck: friendlyBottleneck(profile?.primary_weaknesses),
    updated: profile?.generated_at ? new Date(profile.generated_at).toLocaleDateString() : 'Not analyzed yet',
  }), [profile, user?.analyzed_games]);

  const handleSend = async (event?: FormEvent) => {
    event?.preventDefault();
    const message = input.trim();
    if (!message || isTyping) return;
    setInput('');
    await sendMessage(message);
  };

  const handleNewChat = async () => {
    if (!user?.id) return;
    await initializeSession(user.id);
    setMobileMenuOpen(false);
  };

  const handleStartAnalysis = async () => {
    if (!user?.id || startingAnalysis) return;
    const days = daysForRange(selectedRange, customDays);
    setStartingAnalysis(true);
    try {
      if (days) await api.games.fetchRecent(user.id, { days });
      const result = await api.analysis.analyzeGames(user.id, days ? { days } : undefined);
      setAnalysisOpen(false);
      if (!result.games_queued) {
        toast('Your selected games have already been analyzed.');
        void refetchProfile();
        return;
      }
      toast.success('Analysis started. Your coach will update when it is ready.');
      watchJob(result.job_id ?? undefined, {
        onComplete: () => {
          void refetchProfile();
          void sendMessage('What is the most important improvement opportunity in my latest games?');
        },
        onError: (analysisFailure) => toast.error(`Analysis needs attention: ${analysisFailure.message}`),
      });
    } catch (requestError: unknown) {
      const detail = (requestError as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Could not start analysis. Please try again.');
    } finally {
      setStartingAnalysis(false);
    }
  };

  const handleCancelAnalysis = async () => {
    if (cancellingAnalysis) return;
    setCancellingAnalysis(true);
    try {
      await cancelJob();
      toast.success('Analysis cancelled. You can start a new one whenever you are ready.');
    } catch {
      toast.error('Could not cancel analysis. Please try again.');
    } finally {
      setCancellingAnalysis(false);
    }
  };

  if (loading) return <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a]"><Loader2 className="h-6 w-6 animate-spin text-brand-primary" /></div>;
  if (!user) return <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a] px-6 text-center text-content-muted">Your coaching workspace could not be loaded.</div>;

  return <div className="min-h-screen bg-[#0a0a0a] font-sans text-[#e5e2e1]">
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-80 flex-col bg-[#201f1f] p-7 lg:flex">
      <Brand />
      <button type="button" onClick={() => void handleNewChat()} className="mt-12 flex items-center justify-center gap-3 rounded-lg border border-[#3c4a42] bg-[#2a2a2a] px-4 py-3 font-mono text-sm text-[#e5e2e1] transition-colors hover:border-brand-primary hover:text-brand-primary"><MessageSquarePlus className="h-5 w-5" /> New Chat</button>
      <div className="mt-7 min-h-0 flex-1 overflow-y-auto"><p className="mb-4 px-2 font-mono text-xs uppercase tracking-wider text-[#bbcabf]">Recent</p>{recentSessions.length ? <div className="space-y-1">{recentSessions.map((session) => <button key={session.session_id} type="button" onClick={() => void openSession(session.session_id)} className={`w-full rounded-md px-2 py-2 text-left text-sm transition-colors hover:bg-[#2a2a2a] hover:text-[#e5e2e1] ${session.session_id === sessionId ? 'bg-[#2a2a2a] text-[#e5e2e1]' : 'text-[#bbcabf]'}`}><span className="block truncate">{session.preview}</span></button>)}</div> : <p className="px-2 text-sm leading-6 text-[#bbcabf]">Your coaching conversations will appear here as you continue working with your coach.</p>}</div>
      <div className="mt-auto border-t border-[#3c4a42] pt-5"><button type="button" onClick={() => setAnalysisOpen(true)} disabled={isTracking} className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#10b981] px-4 py-3 font-mono text-sm font-semibold text-[#00422b] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60">{isTracking ? <Loader2 className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />}{isTracking ? 'Analysis Running' : 'Analyze Games'}</button><div className="mt-7 space-y-4 px-2 text-sm text-[#bbcabf]"><span className="flex items-center gap-3"><HelpCircle className="h-4 w-4" /> Help</span><span className="flex items-center gap-3"><Sparkles className="h-4 w-4" /> ChessRun Coach</span></div></div>
    </aside>
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-[#3c4a42] bg-[#131313]/95 px-5 backdrop-blur lg:hidden"><Brand compact /><div className="flex items-center gap-2"><button type="button" aria-label="Analyze games" onClick={() => setAnalysisOpen(true)} disabled={isTracking} className="rounded-md p-2 text-brand-primary hover:bg-[#201f1f] disabled:opacity-60"><BarChart3 className="h-5 w-5" /></button><button type="button" aria-label="Open menu" onClick={() => setMobileMenuOpen((open) => !open)} className="rounded-md p-2 text-[#bbcabf] hover:bg-[#201f1f]"><Menu className="h-5 w-5" /></button></div></header>
    {mobileMenuOpen && <div className="fixed inset-x-0 top-16 z-40 max-h-[70vh] overflow-y-auto border-b border-[#3c4a42] bg-[#201f1f] p-4 lg:hidden"><button type="button" onClick={() => void handleNewChat()} className="flex w-full items-center gap-3 rounded-lg bg-[#2a2a2a] p-3 text-left text-sm"><MessageSquarePlus className="h-4 w-4 text-brand-primary" /> New Chat</button>{recentSessions.length > 0 && <div className="mt-4 border-t border-[#3c4a42] pt-3"><p className="mb-2 font-mono text-xs uppercase text-[#bbcabf]">Recent</p>{recentSessions.map((session) => <button key={session.session_id} type="button" onClick={() => { void openSession(session.session_id); setMobileMenuOpen(false); }} className={`block w-full truncate rounded-md px-3 py-2 text-left text-sm ${session.session_id === sessionId ? 'bg-[#2a2a2a] text-[#e5e2e1]' : 'text-[#bbcabf]'}`}>{session.preview}</button>)}</div>}</div>}
    <main className="mx-auto flex min-h-screen max-w-[1280px] flex-col px-4 pb-32 pt-5 sm:px-6 lg:ml-80 lg:px-12 lg:pt-12"><section className="mx-auto w-full max-w-[940px]"><button type="button" onClick={() => setProfileOpen((open) => !open)} className="flex w-full items-center justify-between rounded-xl border border-t-2 border-[#3c4a42] border-t-brand-primary bg-[#171717] px-5 py-4 text-left"><span className="flex min-w-0 items-center gap-3"><ChevronDown className={`h-4 w-4 shrink-0 text-brand-primary transition-transform ${profileOpen ? 'rotate-180' : ''}`} /><span className="font-mono text-sm font-semibold">Your Playing Profile</span><span className="hidden font-mono text-xs text-[#bbcabf] sm:inline">{profileData.games} Games</span><span className="hidden font-mono text-xs text-[#bbcabf] sm:inline">{profileData.patterns} Patterns</span></span><span className="hidden text-xs text-[#bbcabf] md:block">Updated {profileData.updated}</span></button>{profileOpen && <div className="grid grid-cols-2 gap-5 border-x border-b border-[#3c4a42] bg-[#171717] p-5 text-sm md:grid-cols-4"><ProfileMetric label="Games Analyzed" value={String(profileData.games)} /><ProfileMetric label="Patterns Identified" value={String(profileData.patterns)} /><ProfileMetric label="Strongest Area" value={profileData.strength} positive /><ProfileMetric label="Biggest Bottleneck" value={profileData.bottleneck} warning /></div>}{(status || analysisError) && <AnalysisStatusCard status={status} error={analysisError} cancelling={cancellingAnalysis} onCancel={() => void handleCancelAnalysis()} onAnalyzeAgain={() => setAnalysisOpen(true)} />}</section>
      <section className="mx-auto flex w-full max-w-[940px] flex-1 flex-col pt-10">{isRestoringSession && messages.length === 0 ? <div className="flex flex-1 items-center justify-center text-[#bbcabf]"><Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Restoring your conversation...</div> : <>{messages.length > 0 && <div className="space-y-6">{messages.map((message) => <ChatMessage key={message.id} role={message.role} content={message.content} />)}</div>}{isTyping && <div className="mt-5 flex items-center gap-2 text-sm text-[#bbcabf]"><Bot className="h-4 w-4 text-brand-primary" /><span>Coach is thinking...</span></div>}{error && <p className="mt-4 text-sm text-brand-error">{error}</p>}<div className={`${messages.length ? 'mt-12' : 'my-auto pb-14'} text-center`}>{messages.length === 0 && <><Bot className="mx-auto mb-5 h-9 w-9 text-brand-primary" /><h1 className="text-2xl font-semibold sm:text-[32px]">What should we focus on next?</h1><p className="mx-auto mt-4 max-w-xl text-base leading-7 text-[#bbcabf]">{profile?.profile_summary || 'Analyze your games and I will build a focused coaching profile around the improvement that matters most.'}</p></>}{!hasUserMessage && <div className="mx-auto mt-8 grid max-w-[940px] grid-cols-1 gap-4 md:grid-cols-2">{STARTERS.map(({ title, prompt }) => <button key={title} type="button" onClick={() => setInput(prompt)} className="rounded-lg border border-[#262626] bg-[#171717] p-5 text-left transition-colors hover:border-[#3f3f46] hover:bg-[#201f1f]"><span className="font-mono text-sm font-semibold text-[#e5e2e1]">{title}</span><p className="mt-2 text-sm text-[#bbcabf]">&quot;{prompt}&quot;</p></button>)}</div>}</div></>}</section>
    </main>
    <form onSubmit={handleSend} className="fixed bottom-0 left-0 right-0 z-30 bg-gradient-to-t from-[#0a0a0a] via-[#0a0a0a] to-transparent px-4 pb-5 pt-10 lg:pl-80"><div className="mx-auto max-w-[1000px]"><div className="flex items-center gap-2 rounded-xl border border-[#262626] bg-[#171717] px-3 py-2 focus-within:border-brand-primary"><button type="button" aria-label="Attach a game" className="p-2 text-[#bbcabf] hover:text-[#e5e2e1]"><Paperclip className="h-5 w-5" /></button><input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask your coach anything..." className="min-w-0 flex-1 bg-transparent px-2 py-2 text-sm outline-none placeholder:text-[#bbcabf]" /><button type="submit" disabled={!input.trim() || isTyping} aria-label="Send message" className="p-2 text-[#10b981] disabled:opacity-40"><Send className="h-5 w-5" /></button></div><p className="mt-3 text-center text-xs text-[#bbcabf]">ChessRun AI can make mistakes. Always review critical analysis.</p></div></form>
    {analysisOpen && <AnalysisModal range={selectedRange} customDays={customDays} starting={startingAnalysis} onSelect={setSelectedRange} onCustomDays={setCustomDays} onClose={() => !startingAnalysis && setAnalysisOpen(false)} onStart={() => void handleStartAnalysis()} />}
  </div>;
}

function Brand({ compact = false }: { compact?: boolean }) { return <div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-primary/15 text-brand-primary"><Bot className="h-5 w-5" /></div><div><p className="text-xl font-semibold text-brand-primary">ChessRun</p>{!compact && <p className="text-xs text-[#bbcabf]">AI Grandmaster Coach</p>}</div></div>; }
function ProfileMetric({ label, value, positive, warning }: { label: string; value: string; positive?: boolean; warning?: boolean }) { return <div><p className="font-mono text-[11px] uppercase text-[#bbcabf]">{label}</p><p className={`mt-2 text-sm ${positive ? 'text-brand-primary' : warning ? 'text-[#ffb3af]' : 'text-[#e5e2e1]'}`}>{value}</p></div>; }
function AnalysisStatusCard({ status, error, cancelling, onCancel, onAnalyzeAgain }: { status: AnalysisJobStatus | null; error: Error | null; cancelling: boolean; onCancel: () => void; onAnalyzeAgain: () => void }) {
  const state = status?.status;
  const isRunning = state === 'pending' || state === 'running';
  const isCancelled = state === 'cancelled';
  const isFailure = state === 'failed' || !!error;
  const isPartial = state === 'partial';
  const processed = status ? status.completed_games + status.failed_games : 0;
  const activeNumber = status?.total_games ? Math.min(processed + 1, status.total_games) : 0;
  const title = isRunning ? `Analyzing game ${activeNumber} of ${status?.total_games ?? 0}` : isCancelled ? 'Analysis cancelled' : isFailure ? 'Analysis could not complete' : isPartial ? 'Analysis completed with issues' : 'Analysis complete';
  const detail = isRunning ? `${processed} completed. Your coach will update your Playing Profile when the job finishes.` : isCancelled ? `${status?.completed_games ?? 0} completed games were kept. You can start another analysis whenever you are ready.` : isFailure ? (status?.last_error || error?.message || 'The analysis worker could not process these games.') : isPartial ? `${status?.completed_games ?? 0} games completed; ${status?.failed_games ?? 0} need attention.` : `${status?.completed_games ?? 0} games are now available for coaching.`;
  const Icon = isRunning ? Clock3 : isFailure ? AlertTriangle : CheckCircle2;
  const tone = isFailure ? 'border-[#fc7c78]/50 bg-[#93000a]/20 text-[#ffb4ab]' : isRunning ? 'border-brand-primary/50 bg-brand-primary/10 text-brand-primary' : 'border-brand-primary/50 bg-[#10b981]/10 text-[#6ffbbe]';

  return <div className={`mt-4 rounded-lg border p-4 ${tone}`} role="status"><div className="flex items-start gap-3"><Icon className={`mt-0.5 h-5 w-5 shrink-0 ${isRunning ? 'animate-pulse' : ''}`} /><div className="min-w-0 flex-1"><p className="font-mono text-sm font-semibold">{title}</p><p className="mt-1 text-sm leading-6 text-[#e5e2e1]">{detail}</p>{isRunning && <><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-black/25"><div className="h-full rounded-full bg-brand-primary transition-all" style={{ width: `${Math.max(4, status?.progress_percent ?? 0)}%` }} /></div><button type="button" onClick={onCancel} disabled={cancelling} className="mt-3 font-mono text-xs font-semibold text-[#ffb4ab] underline underline-offset-4 disabled:opacity-50">{cancelling ? 'Cancelling...' : 'Cancel analysis'}</button></>}{(isFailure || isCancelled) && <button type="button" onClick={onAnalyzeAgain} className="mt-3 font-mono text-xs font-semibold underline underline-offset-4">Analyze again</button>}</div></div></div>;
}
function ChatMessage({ role, content }: { role: string; content: string }) { const isUser = role === 'user'; return <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}><div className={`max-w-[85%] ${isUser ? 'rounded-xl border border-[#262626] bg-[#171717]' : 'border-t-2 border-brand-primary'} px-5 py-4 text-sm leading-7 text-[#e5e2e1]`}>{!isUser && <p className="mb-2 font-mono text-xs text-[#bbcabf]">ChessRun Coach</p>}{content}</div></div>; }
function AnalysisModal({ range, customDays, starting, onSelect, onCustomDays, onClose, onStart }: { range: AnalysisRange; customDays: number; starting: boolean; onSelect: (range: AnalysisRange) => void; onCustomDays: (days: number) => void; onClose: () => void; onStart: () => void }) { const choices: Array<{ label: string; value: AnalysisRange; description: string }> = [{ label: 'Analyze All Games', value: 'all', description: 'Every game from your linked account' }, { label: 'Last 7 Days', value: 7, description: 'Recent games' }, { label: 'Last 30 Days', value: 30, description: 'A broader recent sample' }, { label: 'This Month', value: 'month', description: 'Games played this calendar month' }]; return <div className="fixed inset-0 z-50 flex items-end bg-black/70 p-0 backdrop-blur-sm sm:items-center sm:justify-center sm:p-4" role="dialog" aria-modal="true" aria-label="Analyze games"><div className="w-full max-w-lg rounded-t-2xl border border-[#3c4a42] bg-[#201f1f] p-6 shadow-2xl sm:rounded-xl"><div className="mb-6 flex items-start justify-between"><div><p className="font-mono text-xs uppercase tracking-wider text-brand-primary">Select timeframe</p><h2 className="mt-2 text-2xl font-semibold">Analyze Games</h2><p className="mt-2 text-sm leading-6 text-[#bbcabf]">Choose the games that should inform your coaching profile.</p></div><button type="button" onClick={onClose} aria-label="Close" className="p-1 text-[#bbcabf] hover:text-[#e5e2e1]"><X className="h-5 w-5" /></button></div><div className="space-y-2">{choices.map((choice) => <button key={String(choice.value)} type="button" onClick={() => onSelect(choice.value)} className={`flex w-full items-center justify-between rounded-lg border p-4 text-left ${range === choice.value ? 'border-brand-primary bg-brand-primary/10' : 'border-[#262626] bg-[#171717] hover:border-[#3f3f46]'}`}><span><span className="block font-medium">{choice.label}</span><span className="mt-1 block text-xs text-[#bbcabf]">{choice.description}</span></span><ChevronRight className="h-5 w-5 text-brand-primary" /></button>)}<div className={`rounded-lg border p-4 ${range === 'custom' ? 'border-brand-primary bg-brand-primary/10' : 'border-[#262626] bg-[#171717]'}`}><button type="button" onClick={() => onSelect('custom')} className="flex w-full items-center justify-between text-left"><span className="font-medium">Custom Range</span><ChevronRight className="h-5 w-5 text-brand-primary" /></button>{range === 'custom' && <label className="mt-3 block text-sm text-[#bbcabf]">Days to analyze<input type="number" min="1" max="365" value={customDays} onChange={(event) => onCustomDays(Math.max(1, Number(event.target.value)))} className="mt-2 w-full rounded-md border border-[#3c4a42] bg-[#131313] px-3 py-2 text-[#e5e2e1] outline-none focus:border-brand-primary" /></label>}</div></div><div className="mt-6 flex justify-end gap-3"><button type="button" onClick={onClose} disabled={starting} className="px-4 py-2 text-sm text-[#bbcabf] hover:text-[#e5e2e1]">Cancel</button><button type="button" onClick={onStart} disabled={starting} className="flex items-center gap-2 rounded-lg bg-[#10b981] px-4 py-2 text-sm font-semibold text-[#00422b] disabled:opacity-60">{starting && <Loader2 className="h-4 w-4 animate-spin" />}{starting ? 'Starting...' : 'Start Analysis'}</button></div></div></div>; }
