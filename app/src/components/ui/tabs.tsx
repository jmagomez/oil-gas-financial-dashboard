import * as RadixTabs from '@radix-ui/react-tabs';
import type { ComponentPropsWithoutRef } from 'react';
import { cn } from '@/lib/cn';

/**
 * Abas sobre Radix: navegacao por setas, Home/End, foco gerenciado e os
 * `aria-controls`/`aria-selected` corretos vem de graca. Reimplementar isso a
 * mao e onde a acessibilidade de dashboard costuma morrer.
 */
export const Tabs = RadixTabs.Root;

export function TabsList({ className, ...props }: ComponentPropsWithoutRef<typeof RadixTabs.List>) {
  return (
    <RadixTabs.List
      className={cn(
        // Rolagem HORIZONTAL em vez de quebra de linha: com flex-wrap a borda
        // inferior passa a cortar o meio da lista e a aba ativa perde a
        // referencia de "linha de base". As setas do Radix levam o foco para a
        // aba fora de vista e o browser rola ate ela.
        'flex gap-1 overflow-x-auto border-b border-border',
        '[scrollbar-width:thin]',
        className,
      )}
      {...props}
    />
  );
}

export function TabsTrigger({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof RadixTabs.Trigger>) {
  return (
    <RadixTabs.Trigger
      className={cn(
        'relative -mb-px shrink-0 whitespace-nowrap px-3 py-2 text-sm font-medium text-muted',
        'transition-colors hover:text-fg',
        // A aba ativa e marcada por COR e por uma barra inferior: cor sozinha
        // nao serve a quem nao distingue matiz (WCAG 1.4.1).
        'data-[state=active]:text-fg',
        'data-[state=active]:after:absolute data-[state=active]:after:inset-x-0',
        'data-[state=active]:after:-bottom-px data-[state=active]:after:h-0.5',
        'data-[state=active]:after:bg-accent data-[state=active]:after:content-[""]',
        className,
      )}
      {...props}
    />
  );
}

export function TabsContent({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof RadixTabs.Content>) {
  return (
    <RadixTabs.Content className={cn('mt-4 focus-visible:outline-none', className)} {...props} />
  );
}
