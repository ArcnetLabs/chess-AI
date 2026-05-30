import React from 'react';

interface ChessrunPageTitleProps {
  title: string;
  accent?: string;
  subtitle?: string;
}

export const ChessrunPageTitle: React.FC<ChessrunPageTitleProps> = ({
  title,
  accent,
  subtitle,
}) => (
  <header className="mb-8">
    <h1 className="font-display text-4xl font-extrabold tracking-tighter text-content md:text-5xl">
      {title}
      {accent && (
        <>
          <br />
          <span className="text-brand-primary">{accent}</span>
        </>
      )}
    </h1>
    {subtitle && (
      <p className="mt-2 max-w-2xl text-sm tracking-wide text-content-muted">{subtitle}</p>
    )}
  </header>
);
