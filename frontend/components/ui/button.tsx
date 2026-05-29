'use client';

import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

type Variant = 'default' | 'primary' | 'success' | 'danger' | 'ghost' | 'outline';
type Size = 'sm' | 'md' | 'lg' | 'icon';

const VARIANT_CLASSES: Record<Variant, string> = {
  default: 'btn-cozy',
  primary: 'btn-cozy primary',
  success: 'btn-cozy on',
  danger: 'btn-cozy danger',
  ghost: 'btn-cozy ghost',
  outline:
    'btn-cozy bg-transparent border-[1.5px] border-cozy-card-edge text-cozy-ink-soft hover:text-cozy-ink',
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: '!text-[12px] !py-[5px] !px-[10px] !rounded-[12px] !gap-[5px]',
  md: '!text-[14px] !py-[7px] !px-[14px] !rounded-[14px] !gap-[7px]',
  lg: '!text-[15px] !py-[9px] !px-[18px] !rounded-[16px] !gap-2',
  icon: '!w-9 !h-9 !p-0 justify-center',
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
        className={cn(VARIANT_CLASSES[variant], SIZE_CLASSES[size], className)}
        {...props}
      />
    );
  },
);
Button.displayName = 'Button';
