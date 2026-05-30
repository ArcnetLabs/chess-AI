export function formatRelativeTime(isoDate: string | undefined): string {
  if (!isoDate) return '—';
  const then = new Date(isoDate).getTime();
  if (Number.isNaN(then)) return '—';
  const diffMs = Date.now() - then;
  const diffMins = Math.floor(diffMs / 60_000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  return new Date(isoDate).toLocaleDateString();
}
