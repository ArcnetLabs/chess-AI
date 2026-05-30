import React from 'react';
import { ChessrunAppShell } from './ChessrunAppShell';
import { ChessrunPageTitle } from './ChessrunPageTitle';

interface ChessrunPageShellProps {
  children: React.ReactNode;
  title?: string;
  accent?: string;
  subtitle?: string;
  maxWidth?: 'md' | 'lg' | 'xl' | '7xl';
}

/**
 * Authenticated app chrome: sidebar, top bar, mobile nav.
 * Dashboard supplies its own hero; other pages may pass title/accent/subtitle.
 */
export const ChessrunPageShell: React.FC<ChessrunPageShellProps> = ({
  children,
  title,
  accent,
  subtitle,
  maxWidth = '7xl',
}) => {
  const maxClass =
    maxWidth === 'md'
      ? 'max-w-md'
      : maxWidth === 'lg'
        ? 'max-w-lg'
        : maxWidth === 'xl'
          ? 'max-w-xl'
          : 'max-w-7xl';

  return (
    <ChessrunAppShell>
      <div className={`mx-auto w-full ${maxClass}`}>
        {title && <ChessrunPageTitle title={title} accent={accent} subtitle={subtitle} />}
        {children}
      </div>
    </ChessrunAppShell>
  );
};
