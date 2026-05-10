'use client';

import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

type Variant = 'default' | 'primary' | 'success' | 'danger' | 'ghost' | 'outline';
type Size = 'sm' | 'md' | 'lg' | 'icon';

const VARIANT_CLASSES: Record<Variant, string> = {
  default:
    'bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700/80 hover:border-zinc-600',
  primary:
    'bg-blue-600 hover:bg-blue-500 text-white border border-blue-500/40 shadow-sm shadow-blue-900/30',
  success:
    'bg-emerald-600 hover:bg-emerald-500 text-white border border-emerald-500/40 shadow-sm shadow-emerald-900/30',
  danger:
    'bg-red-600 hover:bg-red-500 text-white border border-red-500/40 shadow-sm shadow-red-900/30',
  ghost:
    'bg-transparent text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/70 border border-transparent',
  outline:
    'bg-transparent text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800 border border-zinc-700',
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: 'h-7 px-2.5 text-xs gap-1.5',
  md: 'h-8 px-3 text-sm gap-1.5',
  lg: 'h-10 px-4 text-sm gap-2',
  icon: 'h-8 w-8 p-0 justify-center',
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'md', type = 'button', ...props }, ref) => {
    return (
      <button
        ref={ref}
        type={type}
        className={cn(
          'inline-flex items-center justify-center rounded-md font-medium transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950',
          'disabled:pointer-events-none disabled:opacity-40',
          'whitespace-nowrap',
          VARIANT_CLASSES[variant],
          SIZE_CLASSES[size],
          className,
        )}
        {...props}
      />
    );
  },
);
Button.displayName = 'Button';
