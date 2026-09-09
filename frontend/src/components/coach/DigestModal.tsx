import { useCallback, useEffect, useState } from 'react';
import { CalendarClock, Loader2, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { notificationsApi, type NotificationItem } from '@/lib/api';

function notificationIdLabel(type: string): string {
  if (type === 'weekly_digest') return 'Weekly digest';
  if (type === 'interview_summary') return 'Interview recap';
  return type.replace(/_/g, ' ');
}

function notificationDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
}

export function DigestModal({
  userId,
  onClose,
}: {
  userId: number;
  onClose: () => void;
}) {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await notificationsApi.list(userId, { limit: 30 });
      setItems(response.notifications);
      setUnreadCount(response.unread_count);
    } catch {
      setError('Could not load your digest. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void load();
  }, [load]);

  const digestFirst = [...items].sort((a, b) => {
    const aPriority = a.notification_type === 'weekly_digest' ? 0 : 1;
    const bPriority = b.notification_type === 'weekly_digest' ? 0 : 1;
    if (aPriority !== bPriority) return aPriority - bPriority;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  const handleMarkRead = async (notification: NotificationItem) => {
    setBusyId(notification.id);
    try {
      await notificationsApi.markRead(userId, notification.id);
      setItems((current) =>
        current.map((item) =>
          item.id === notification.id
            ? { ...item, is_read: true, read_at: new Date().toISOString() }
            : item,
        ),
      );
      setUnreadCount((current) => Math.max(0, current - 1));
    } catch {
      toast.error('Could not mark this digest as read.');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end bg-black/70 p-0 backdrop-blur-sm sm:items-center sm:justify-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Weekly digest"
    >
      <div className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-t-2xl border border-[#3c4a42] bg-[#201f1f] p-6 shadow-2xl sm:rounded-xl">
        <div className="mb-6 flex items-start justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-wider text-brand-primary">
              Proactive loop
            </p>
            <h2 className="mt-2 flex items-center gap-2 text-2xl font-semibold">
              <CalendarClock className="h-6 w-6 text-brand-primary" /> Weekly Coaching Loop
            </h2>
            <p className="mt-2 text-sm leading-6 text-[#bbcabf]">
              Your coach compiles what changed and what deserves focus — new every week after
              fresh game analyses.
              {unreadCount > 0 && (
                <span className="ml-2 font-mono text-xs text-brand-primary">
                  {unreadCount} unread
                </span>
              )}
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
        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          {loading ? (
            <div className="flex items-center justify-center py-10 text-sm text-[#bbcabf]">
              <Loader2 className="mr-2 h-4 w-4 animate-spin text-brand-primary" /> Loading your
              digest...
            </div>
          ) : error ? (
            <p className="py-6 text-center text-sm text-brand-error">{error}</p>
          ) : items.length === 0 ? (
            <p className="py-10 text-center text-sm leading-6 text-[#bbcabf]">
              Nothing here yet. After each analysis run your coach compiles a weekly digest of
              changes, focus areas, and drills — it will appear here.
            </p>
          ) : (
            <ul className="space-y-3">
              {digestFirst.map((item) => (
                <DigestCard
                  key={item.id}
                  item={item}
                  busy={busyId === item.id}
                  onMarkRead={() => void handleMarkRead(item)}
                />
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function DigestCard({
  item,
  busy,
  onMarkRead,
}: {
  item: NotificationItem;
  busy: boolean;
  onMarkRead: () => void;
}) {
  return (
    <li
      className={`rounded-lg border px-4 py-3 ${
        item.is_read
          ? 'border-[#262626] bg-[#171717] opacity-80'
          : 'border-brand-primary/40 bg-[#171717]'
      }`}
    >
      <p className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wide text-[#bbcabf]">
        <span className={item.is_read ? '' : 'text-brand-primary'}>{notificationIdLabel(item.notification_type)}</span>
        <span className="ml-auto normal-case tracking-normal">{notificationDate(item.created_at)}</span>
      </p>
      <p className="mt-1.5 font-mono text-sm font-semibold text-[#e5e2e1]">{item.title}</p>
      {item.body && (
        <p className="mt-1 whitespace-pre-line text-sm leading-6 text-[#e5e2e1]">{item.body}</p>
      )}
      {!item.is_read && (
        <button
          type="button"
          onClick={onMarkRead}
          disabled={busy}
          className="mt-3 font-mono text-xs font-semibold text-brand-primary underline underline-offset-4 disabled:opacity-50"
        >
          {busy ? 'Marking...' : 'Mark as read'}
        </button>
      )}
    </li>
  );
}
