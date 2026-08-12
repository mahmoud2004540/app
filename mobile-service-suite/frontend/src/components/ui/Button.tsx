import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  children: ReactNode;
}

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-brand-500 text-white hover:bg-brand-600 disabled:bg-brand-500/50',
  secondary:
    'border border-slate-200 bg-white text-slate-700 hover:bg-slate-100 ' +
    'dark:border-surface-border dark:bg-surface-overlay dark:text-slate-200 dark:hover:bg-surface-border',
  ghost:
    'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-surface-overlay',
};

export function Button({
  variant = 'primary',
  children,
  className = '',
  ...props
}: ButtonProps): JSX.Element {
  return (
    <button
      className={
        'inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium ' +
        'transition-colors disabled:cursor-not-allowed ' +
        VARIANTS[variant] +
        ' ' +
        className
      }
      {...props}
    >
      {children}
    </button>
  );
}
