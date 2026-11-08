import { useMemo, useState } from 'react';
import { useDados } from '@/hooks/use-dados';
import { Card, CardNote, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ChartContainer } from '@/components/charts/chart-container';
import { GraficoRadar } from '@/components/charts/grafico-radar';
import { decimal } from '@/lib/formatters';

/** Cores distinguiveis; o rotulo tambem aparece na legenda e na tabela. */
const CORES = [
  'hsl(var(--accent))',
  'hsl(var(--down))',
  'hsl(var(--warn))',
  'hsl(var(--up))',
] as const;

/** Mais de quatro perfis sobrepostos deixam o radar ilegivel. */
const MAX_SELECAO = 4;

export function PainelPerfil() {
  const { data, isPending, error } = useDados();
  const [selecao, setSelecao] = useState<string[]>([]);

  const escolhidas = useMemo(() => {
    const padrao = (data?.empresas ?? []).slice(0, 3).map((e) => e.ticker);
    return selecao.length > 0 ? selecao : padrao;
  }, [data, selecao]);

  const dadosRadar = useMemo(() => {
    if (!data) return [];
    return data.meta_build.eixos_perfil.map((eixo) => {
      const linha: Record<string, string | number> = { eixo };
      for (const e of data.empresas) {
        if (escolhidas.includes(e.ticker)) linha[e.ticker] = e.perfil[eixo] ?? 0;
      }
      return linha;
    });
  }, [data, escolhidas]);

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (error || !data) {
    return (
      <Card>
        <CardTitle>Perfil comparativo</CardTitle>
        <CardNote className="mt-1">
          {error instanceof Error ? error.message : 'dados indisponíveis'}
        </CardNote>
      </Card>
    );
  }

  // Capturado depois do guard: dentro do callback de `alterna` o TypeScript
  // nao consegue estreitar `data`, porque o callback pode rodar depois.
  const empresas = data.empresas;

  const series = escolhidas.map((t, i) => ({
    rotulo: t,
    cor: CORES[i % CORES.length] ?? 'hsl(var(--accent))',
  }));

  function alterna(ticker: string) {
    setSelecao((atual) => {
      const base = atual.length > 0 ? atual : empresas.slice(0, 3).map((e) => e.ticker);
      if (base.includes(ticker)) {
        // Nunca deixa zerar: radar sem serie e um hexagono vazio.
        return base.length === 1 ? base : base.filter((t) => t !== ticker);
      }
      return base.length >= MAX_SELECAO ? base : [...base, ticker];
    });
  }

  return (
    <div className="grid gap-4">
      <Card>
        <CardTitle>Perfil comparativo</CardTitle>
        <CardNote className="mt-1">
          Até {MAX_SELECAO} empresas por vez — acima disso os perfis sobrepostos deixam de ser
          legíveis.
        </CardNote>
        <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Empresas no radar">
          {data.empresas.map((e) => {
            const ativa = escolhidas.includes(e.ticker);
            return (
              <button
                key={e.ticker}
                type="button"
                aria-pressed={ativa}
                onClick={() => alterna(e.ticker)}
                className={
                  ativa
                    ? 'rounded-lg border border-accent bg-accent px-2.5 py-1 text-xs font-semibold text-bg'
                    : 'rounded-lg border border-border px-2.5 py-1 text-xs text-muted transition-colors hover:text-fg'
                }
              >
                {e.ticker}
              </button>
            );
          })}
        </div>
      </Card>

      <ChartContainer
        titulo="Radar de perfil"
        unidade="escala 0–100 relativa ao grupo, não absoluta"
        descricao={`Radar de ${escolhidas.join(', ')} em ${
          data.meta_build.eixos_perfil.length
        } eixos normalizados de 0 a 100: ${dadosRadar
          .map(
            (l) =>
              `${String(l['eixo'])} — ${escolhidas
                .map((t) => `${t} ${decimal(Number(l[t]))}`)
                .join(', ')}`,
          )
          .join('; ')}`}
        tabela={{
          colunas: [
            { chave: 'eixo', rotulo: 'Eixo' },
            ...escolhidas.map((t) => ({ chave: t, rotulo: t })),
          ],
          linhas: dadosRadar.map((l) => {
            const linha: Record<string, string> = { eixo: String(l['eixo']) };
            for (const t of escolhidas) linha[t] = decimal(Number(l[t]));
            return linha;
          }),
        }}
        nota={
          <>
            <b>Posição relativa, não magnitude.</b> Cada eixo é normalizado por min-max entre as
            sete empresas: o melhor do grupo recebe 100 e o pior 0 em <i>todo</i> eixo, com
            dispersão real de 2× ou de 50×. Serve para comparar o <i>formato</i> de dois perfis, não
            para medir distância — para magnitude, use os painéis de eficiência e valuation.
            <br />
            <br />
            <b>E cuidado com o eixo Valuation.</b> Ele pontua múltiplo baixo como alto, então a
            Petrobras aparece com 100 em Rentabilidade, Valuation e Retorno ao acionista — e 0 em
            Solidez. Isso não diz que ela é a melhor do grupo: múltiplo baixo é o preço que o
            mercado cobra por risco estatal, câmbio e um regime fiscal e de dividendos diferente.
            Com sete empresas, basta uma no extremo para comprimir todas as outras.
          </>
        }
      >
        <GraficoRadar dados={dadosRadar} series={series} />
      </ChartContainer>
    </div>
  );
}
