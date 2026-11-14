import { useMemo } from 'react';
import { useDados } from '@/hooks/use-dados';
import { Card, CardNote, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ChartContainer } from '@/components/charts/chart-container';
import { GraficoDispersao } from '@/components/charts/grafico-dispersao';
import { decimal, multiplo, percentual, milhoes, data as fmtData, AUSENTE } from '@/lib/formatters';

export function PainelValuation() {
  const { data, isPending, error } = useDados();

  /** EV/EBITDA x ROE, bolha = market cap. Precisa dos tres campos. */
  const multiploRetorno = useMemo(
    () =>
      (data?.empresas ?? [])
        .map((e) => ({
          rotulo: e.ticker,
          x: e.fy2025.derivados.ev_ebitda_x,
          y: e.fy2025.roe_pct,
          z: e.mercado.market_cap,
        }))
        .filter(
          (p): p is { rotulo: string; x: number; y: number; z: number } =>
            p.x !== null && p.y !== null && p.z !== null,
        ),
    [data],
  );

  /** Dividend yield x FCF yield. Acima da diagonal, o caixa cobre o dividendo. */
  const yields = useMemo(
    () =>
      (data?.empresas ?? [])
        .map((e) => ({
          rotulo: e.ticker,
          x: e.mercado.dividend_yield_pct,
          y: e.fy2025.derivados.fcf_yield_pct,
        }))
        .filter((p): p is { rotulo: string; x: number; y: number } => p.x !== null && p.y !== null),
    [data],
  );

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (error || !data) {
    return (
      <Card>
        <CardTitle>Valuation e retorno ao acionista</CardTitle>
        <CardNote className="mt-1">
          {error instanceof Error ? error.message : 'dados indisponíveis'}
        </CardNote>
      </Card>
    );
  }

  const naoCobrem = yields.filter((p) => p.y < p.x).map((p) => p.rotulo);

  return (
    <div className="grid gap-4">
      <Card>
        <CardTitle>Valuation e retorno ao acionista</CardTitle>
        <CardNote className="mt-1">
          Múltiplos de mercado são <i>snapshot</i> de {fmtData(data.referencia.atualizado_em)} e
          valem igualmente para as duas colunas de período — não são do fechamento do ano fiscal.
        </CardNote>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartContainer
          titulo="Múltiplo contra retorno"
          unidade="EV/EBITDA (×) no eixo X, ROE (%) no eixo Y · área da bolha = market cap"
          descricao={`Dispersão de EV sobre EBITDA contra ROE: ${multiploRetorno
            .map((p) => `${p.rotulo} ${decimal(p.x)}x e ${percentual(p.y)}`)
            .join('; ')}`}
          tabela={{
            colunas: [
              { chave: 'empresa', rotulo: 'Empresa' },
              { chave: 'ev', rotulo: 'EV/EBITDA' },
              { chave: 'roe', rotulo: 'ROE' },
              { chave: 'cap', rotulo: 'Market cap (US$ mi)' },
            ],
            linhas: multiploRetorno.map((p) => ({
              empresa: p.rotulo,
              ev: multiplo(p.x),
              roe: percentual(p.y),
              cap: milhoes(p.z),
            })),
          }}
          nota={
            <>
              Canto superior esquerdo é o lugar desejável: retorno alto pagando múltiplo baixo. Mas
              múltiplo baixo não é desconto gratuito — costuma ser o preço de um risco que o mercado
              está cobrando.
            </>
          }
        >
          <GraficoDispersao
            dados={multiploRetorno}
            rotuloX="EV/EBITDA (×)"
            rotuloY="ROE (%)"
            formataX={(v) => decimal(v)}
            formataY={(v) => percentual(v, 0)}
          />
        </ChartContainer>

        <ChartContainer
          titulo="Dividend yield contra FCF yield"
          unidade="% · acima da diagonal, o caixa livre cobre o dividendo"
          descricao={`Dispersão de dividend yield contra FCF yield: ${yields
            .map((p) => `${p.rotulo} paga ${percentual(p.x)} e gera ${percentual(p.y)}`)
            .join('; ')}`}
          tabela={{
            colunas: [
              { chave: 'empresa', rotulo: 'Empresa' },
              { chave: 'dy', rotulo: 'Dividend yield' },
              { chave: 'fcfy', rotulo: 'FCF yield' },
              { chave: 'cob', rotulo: 'Cobertura' },
            ],
            linhas: yields.map((p) => ({
              empresa: p.rotulo,
              dy: percentual(p.x),
              fcfy: percentual(p.y),
              cob: p.x === 0 ? AUSENTE : multiplo(p.y / p.x),
            })),
          }}
          nota={
            <>
              {naoCobrem.length > 0 && (
                <>
                  <b>{naoCobrem.join(', ')} abaixo da diagonal:</b> o caixa livre do período não
                  cobre o dividendo pago. Num setor cíclico isso é comum no vale e não significa
                  corte iminente — mas sustentado por vários períodos, significa.{' '}
                </>
              )}
              <b>O yield da Petrobras é uma faixa, não um número.</b> O próprio payload registra que
              as fontes divergem entre ~5% e ~9% por metodologia (<i>forward</i> contra{' '}
              <i>trailing</i>, PBR contra PBR.A) e pela política de proventos extraordinários.
              Ranquear por este campo sem a ressalva produz conclusão errada com número certo.
            </>
          }
        >
          <GraficoDispersao
            dados={yields}
            rotuloX="Dividend yield (%)"
            rotuloY="FCF yield (%)"
            formataX={(v) => percentual(v, 0)}
            formataY={(v) => percentual(v, 0)}
          />
        </ChartContainer>
      </div>
    </div>
  );
}
