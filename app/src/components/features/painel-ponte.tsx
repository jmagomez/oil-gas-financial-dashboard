import { useMemo, useState } from 'react';
import { useDados } from '@/hooks/use-dados';
import { Card, CardNote, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { SeletorPeriodo } from '@/components/ui/seletor-periodo';
import { ChartContainer } from '@/components/charts/chart-container';
import { GraficoPonte } from '@/components/charts/grafico-ponte';
import { montaPonte } from '@/lib/ponte';
import { bloco, rotuloPeriodo, type Periodo } from '@/types/dashboard-data';
import { milhoes } from '@/lib/formatters';

const COLUNAS = [
  { chave: 'passo', rotulo: 'Passo' },
  { chave: 'valor', rotulo: 'Valor (US$ mi)' },
  { chave: 'acumulado', rotulo: 'Acumulado' },
] as const;

export function PainelPonte() {
  const { data, isPending, error } = useDados();
  const [ticker, setTicker] = useState<string | null>(null);
  const [periodo, setPeriodo] = useState<Periodo>('fy2025');

  const empresa = useMemo(
    () => data?.empresas.find((e) => e.ticker === (ticker ?? data.empresas[0]?.ticker)),
    [data, ticker],
  );
  const ponte = useMemo(
    () => (empresa ? montaPonte(bloco(empresa, periodo)) : null),
    [empresa, periodo],
  );

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (error || !data || !empresa) {
    return (
      <Card>
        <CardTitle>Ponte de caixa</CardTitle>
        <CardNote className="mt-1">
          {error instanceof Error ? error.message : 'dados indisponíveis'}
        </CardNote>
      </Card>
    );
  }

  return (
    <div className="grid gap-4">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle>Ponte de caixa</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs text-muted" htmlFor="ponte-empresa">
              Empresa
            </label>
            <select
              id="ponte-empresa"
              value={empresa.ticker}
              onChange={(ev) => setTicker(ev.target.value)}
              className="rounded-lg border border-border bg-surface px-2 py-1 text-xs"
            >
              {data.empresas.map((e) => (
                <option key={e.ticker} value={e.ticker}>
                  {e.ticker} — {e.nome}
                </option>
              ))}
            </select>
            <SeletorPeriodo
              valor={periodo}
              onChange={setPeriodo}
              rotuloTrimestre={empresa.q_recente.trimestre}
            />
          </div>
        </div>
        <CardNote className="mt-1">
          {empresa.nome} · {rotuloPeriodo(empresa, periodo)}
        </CardNote>
      </Card>

      {ponte === null ? (
        <Card>
          <CardNote>Algum campo do período está ausente — a ponte não pode ser montada.</CardNote>
        </Card>
      ) : (
        <ChartContainer
          titulo="Da receita ao caixa livre"
          unidade="US$ milhões"
          descricao={`Ponte de caixa de ${empresa.nome} em ${rotuloPeriodo(
            empresa,
            periodo,
          )}: ${ponte.passos.map((p) => `${p.rotulo} ${milhoes(p.delta)}`).join('; ')}`}
          tabela={{
            colunas: COLUNAS,
            linhas: ponte.passos.map((p) => ({
              passo: p.rotulo,
              valor: milhoes(p.delta),
              acumulado: milhoes(p.acumulado),
            })),
          }}
          nota={
            <>
              Cada passo é uma subtração entre campos do mesmo período — nada aqui é estimado.{' '}
              <b>Capital de giro, impostos e juros aparecem juntos</b> porque a fonte não os abre em
              campos separados; inventar a abertura seria afirmar números que ela não tem.
              {ponte.residuo !== 0 && (
                <>
                  {' '}
                  <b>
                    Resíduo de US$ {milhoes(ponte.residuo)} mi
                    {ponte.residuoRelevante ? ' — acima de arredondamento' : ' (arredondamento)'}.
                  </b>{' '}
                  O FCF publicado não é exatamente FCO + capex. As barras não são forçadas a fechar:
                  ajustá-las esconderia a diferença.
                </>
              )}
            </>
          }
        >
          <GraficoPonte ponte={ponte} />
        </ChartContainer>
      )}
    </div>
  );
}
