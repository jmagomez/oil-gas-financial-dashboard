import { Component, type ErrorInfo, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Card, CardNote, CardTitle } from '@/components/ui/card';

const client = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

export function Providers({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

interface Estado {
  erro: Error | null;
}

/**
 * Fronteira de erro POR PAINEL, nao uma global: um payload inesperado num
 * painel nao pode apagar a tela inteira.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, Estado> {
  override state: Estado = { erro: null };

  static getDerivedStateFromError(erro: Error): Estado {
    return { erro };
  }

  override componentDidCatch(erro: Error, info: ErrorInfo) {
    console.error('painel falhou', erro, info.componentStack);
  }

  override render() {
    if (this.state.erro) {
      return (
        <Card role="alert" className="border-down/40 bg-down/10">
          <CardTitle>Este painel falhou</CardTitle>
          <CardNote className="mt-1">{this.state.erro.message}</CardNote>
        </Card>
      );
    }
    return this.props.children;
  }
}
