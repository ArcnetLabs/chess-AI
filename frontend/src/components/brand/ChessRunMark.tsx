/**
 * ChessRun brand mark.
 *
 * A knight (the fastest of the chess pieces — it jumps where others walk)
 * with motion lines: chess + run. Pure inline SVG so it inherits color.
 */

export function KnightGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <path
        d="M11.5 25.5c-.4-1.6-.3-3.4.5-5.2 1-2.3 3-4.5 5-6.4l-1.9-1.4c-.8.9-2.2 1.6-3.2 1.3-.8-.2-1.1-1-1.5-1.4 1.4-2.2 3.1-3.4 5.3-4.4 2.6-1.2 5.5-.6 7.4 1.3 2.4 2.4 2.6 6.3 1 9.6-1.5 3.2-3.6 5-3.9 6.6H11.5Z"
        fill="currentColor"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path
        d="M10.8 9.2 8.6 6.4m3.9 1.4-1.3-2.4"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <path
        d="M9 25.5h13.5"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
      <path
        d="M6.5 21.5c.9-2.5 2.4-4.6 4.4-6.2M5 17c1.2-2.4 3-4.4 5.3-5.8"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        opacity="0.45"
      />
    </svg>
  );
}

export function ChessRunMark({
  className,
  compactWordmark = false,
}: {
  className?: string;
  compactWordmark?: boolean;
}) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className ?? ''}`}>
      <KnightGlyph className="h-8 w-8 text-brand-primary" />
      <span
        className={`font-display font-semibold tracking-tight ${
          compactWordmark ? 'text-lg' : 'text-xl'
        } text-[#e5e2e1]`}
      >
        chess<span className="text-brand-primary">run</span>
      </span>
    </span>
  );
}
