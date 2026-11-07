import { lazy, Suspense } from 'react';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorBoundary } from '@/app/providers';
import { useIndicadores } from '@/hooks/use-indicadores';
import { data } from '@/lib/formatters';

/**
 * O painel entra por import DINAMICO. O Recharts, quando os graficos chegarem,
 * pesa mais que o payload inteiro -- deixa-lo fora do bundle de entrada e o que
 * mantem a primeira tela leve. O padrao fica estabelecido desde o primeiro
 * painel para nao ser retrofit depois.
 */
const PainelComparativo = lazy(() =>
  import('@/components/features/painel-comparativo').then((m) => ({
    default: m.PainelComparativo,
  })),
);

function Carregando() {
  return (
    <div role="status" aria-live="polite" aria-busy="true" className="grid gap-4">
      <span className="sr-only">Carregando painel…</span>
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function Cabecalho() {
  const { data: payload } = useIndicadores();
  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-xl font-bold tracking-tight sm:text-2xl">Dashboard Óleo &amp; Gás</h1>
        <p className="mt-1 text-sm text-muted">
          {payload
            ? `${payload.empresas.length} petroleiras · dados de ${data(payload.referencia.atualizado_em)}`
            : 'Carregando os indicadores…'}
        </p>
      </div>
      <ThemeToggle />
    </header>
  );
}

function Rodape() {
  return (
    <footer className="mt-10 border-t border-border pt-4 text-xs leading-relaxed text-muted">
      <p>
        <b>Esta é a camada nova.</b> O dashboard completo, com todos os gráficos, continua em{' '}
        <a className="text-accent underline" href="../dashboard_oleo_gas.html">
          dashboard_oleo_gas.html
        </a>
        . As análises migram uma a uma; nada sai do ar antes de ter substituto aqui.
      </p>
      <p className="mt-2">
        <b>Ausente não é zero.</b> Campo que a fonte não trouxe aparece como travessão, nunca como
        zero — a produção da Equinor em 2025 é o caso presente hoje.
      </p>
      <p className="mt-2">
        <b>Derivados vêm do pipeline.</b> Os indicadores são calculados por{' '}
        <code>build_dashboard.py</code>, não aqui. Este app deriva apenas leitura: posição na faixa
        histórica, rótulo e quando uma estimativa não é confiável.
      </p>
      <p className="mt-2">Conteúdo informativo. Não constitui recomendação de investimento.</p>
    </footer>
  );
}

export function App() {
  return (
    <div className="min-h-screen">
      <a
        href="#conteudo"
        className="sr-only-focusable absolute left-3 top-3 z-50 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-bg"
      >
        Pular para o conteúdo
      </a>
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Cabecalho />
        <main id="conteudo" className="mt-5">
          <ErrorBoundary>
            <Suspense fallback={<Carregando />}>
              <PainelComparativo />
            </Suspense>
          </ErrorBoundary>
        </main>
        <Rodape />
      </div>
    </div>
  );
}
