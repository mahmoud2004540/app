import type { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
}

/** Themed surface container used across pages. */
export function Card({ children, className = '' }: CardProps): JSX.Element {
  return (
    <div
      className={
        'rounded-xl border border-slate-200 bg-white p-5 shadow-sm ' +
        'dark:border-surface-border dark:bg-surface-raised dark:shadow-lg ' +
        className
      }
    >
      {children}
    </div>
  );
}
