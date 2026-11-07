import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

/**
 * Dimensionado por quem usa, com a altura do conteudo real: skeleton menor que
 * o conteudo causa salto de layout na troca, que e pior que nao ter skeleton.
 */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden
      className={cn('animate-pulse rounded-lg bg-border/60', className)}
      {...props}
    />
  );
}
