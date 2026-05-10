'use client';

import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogPortal = DialogPrimitive.Portal;
export const DialogClose = DialogPrimitive.Close;

export const DialogOverlay = forwardRef<
  ElementRef<typeof DialogPrimitive.Overlay>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      'fixed inset-0 z-40 bg-black/75 backdrop-blur-sm',
      'data-[state=open]:animate-fade-in data-[state=closed]:animate-fade-out',
      className,
    )}
    {...props}
  />
));
DialogOverlay.displayName = 'DialogOverlay';

type DialogContentProps = ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  showClose?: boolean;
};

const SIZE_CLASSES: Record<NonNullable<DialogContentProps['size']>, string> = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
};

export const DialogContent = forwardRef<
  ElementRef<typeof DialogPrimitive.Content>,
  DialogContentProps
>(({ className, children, size = 'lg', showClose = true, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        'fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2',
        'rounded-2xl border border-zinc-700/70 bg-zinc-900 shadow-2xl shadow-black/40',
        'data-[state=open]:animate-dialog-in data-[state=closed]:animate-dialog-out',
        'max-h-[90vh] overflow-y-auto',
        SIZE_CLASSES[size],
        className,
      )}
      {...props}
    >
      {children}
      {showClose && (
        <DialogPrimitive.Close
          aria-label="Close"
          className="absolute right-3 top-3 rounded-md p-1.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-600"
        >
          <X className="h-4 w-4" />
        </DialogPrimitive.Close>
      )}
    </DialogPrimitive.Content>
  </DialogPortal>
));
DialogContent.displayName = 'DialogContent';

export function DialogHeader({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('px-6 pt-6 pb-2', className)}>{children}</div>;
}

export function DialogTitle({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <DialogPrimitive.Title className={cn('text-lg font-semibold text-zinc-100', className)}>
      {children}
    </DialogPrimitive.Title>
  );
}

export function DialogDescription({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <DialogPrimitive.Description className={cn('mt-1 text-sm text-zinc-400', className)}>
      {children}
    </DialogPrimitive.Description>
  );
}

export function DialogBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('px-6 py-4', className)}>{children}</div>;
}

export function DialogFooter({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('flex items-center justify-end gap-2 border-t border-zinc-800/80 px-6 py-3', className)}>
      {children}
    </div>
  );
}
