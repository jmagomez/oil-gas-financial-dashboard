import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/cn';

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-surface p-4',
        'transition-colors duration-theme',
        className,
      )}
      {...props}
    />
  );
}

/**
 * `children` obrigatorio: titulo de card vazio ja aconteceu, e um card sem
 * titulo e indistinguivel de um card quebrado.
 */
export function CardTitle({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLHeadingElement> & { children: ReactNode }) {
  return (
    <h3 className={cn('text-sm font-semibold', className)} {...props}>
      {children}
    </h3>
  );
}

export function CardNote({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-xs leading-relaxed text-muted', className)} {...props} />;
}
