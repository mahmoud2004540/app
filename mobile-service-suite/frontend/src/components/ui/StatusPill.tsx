import type { ReactNode } from 'react';

export type StatusTone = 'good' | 'warning' | 'error' | 'info' | 'neutral';

const TONES: Record<StatusTone, string> = {
  good: 'bg-status-good/15 text-status-good',
  warning: 'bg-status-warning/15 text-status-warning',
  error: 'bg-status-error/15 text-status-error',
  info: 'bg-status-info/15 text-status-info',
  neutral: 'bg-slate-400/15 text-slate-500 dark:text-slate-400',
};

const DOT: Record<StatusTone, string> = {
  good: 'bg-status-good',
  warning: 'bg-status-warning',
  error: 'bg-status-error',
  info: 'bg-status-info',
  neutral: 'bg-slate-400',
};

interface StatusPillProps {
  tone: StatusTone;
  children: ReactNode;
  withDot?: boolean;
}

/** Small colored status chip used throughout diagnostics views. */
export function StatusPill({ tone, children, withDot = true }: StatusPillProps): JSX.Element {
  return (
    <span
      className={
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ' +
        TONES[tone]
      }
    >
      {withDot && <span className={'h-1.5 w-1.5 rounded-full ' + DOT[tone]} />}
      {children}
    </span>
  );
}
