import { useMemo } from 'react';
import { useDados } from '@/hooks/use-dados';
import { Card, CardNote, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { CelulaAlavancagem } from './celula-alavancagem';
import { alavancagem, faixaHistorica, serieDoHistorico } from '@/lib/derivacoes';
import { milhoes, percentual, multiplo, trimestreCurto, data, AUSENTE } from '@/lib/formatters';

export function PainelComparativo() {
  // Payload ENRIQUECIDO, nao o curado. A coluna EV/EBITDA precisa de
  // `derivados.ev_ebitda_x`, que so o build_dashboard.py calcula; derivar a
  // formula aqui em TS criaria a segunda implementacao que o derivacoes.ts
  // proibe de proposito. Os outros quatro paineis ja usam este hook.
  const { data: payload, isPending, error } = useDados();

  const linhas = useMemo(
    () =>
      (payload?.empresas ?? []).map((e) => {
        const serieEbitda = serieDoHistorico(e.historico, 'ebitda');
        return {
          empresa: e,
          alav: alavancagem(e.fy2025),
          faixaEbitda: faixaHistorica(serieEbitda, e.q_recente.ebitda),
        };
      }),
    [payload],
  );

  if (isPending) {
    return (
      <div role="status" aria-live="polite" aria-busy="true" className="grid gap-4">
        <span className="sr-only">Carregando indicadores…</span>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !payload) {
    return (
      <Card>
        <CardTitle>Indicadores</CardTitle>
        <CardNote className="mt-1">
          Não foi possível carregar: {error instanceof Error ? error.message : 'erro desconhecido'}
        </CardNote>
      </Card>
    );
  }

  return (
    <div className="grid gap-4">
      <Card>
        <CardTitle>Comparativo — ano fiscal 2025</CardTitle>
        <CardNote className="mt-1">
          Dados v{payload.referencia.versao_dados}, atualizados em{' '}
          {data(payload.referencia.atualizado_em)}. Valores em US$ milhões.
        </CardNote>

        <div className="mt-3 overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[52rem] text-sm">
            <caption className="sr-only">
              Receita, EBITDA, free cash flow, alavancagem e múltiplos por empresa no ano fiscal
              2025, com a posição do EBITDA do último trimestre dentro da faixa histórica de cada
              empresa
            </caption>
            <thead className="bg-bg text-xs text-muted">
              <tr>
                <th scope="col" className="px-3 py-2 text-left font-medium">
                  Empresa
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  Receita
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  EBITDA
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  FCF
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  Margem líq.
                </th>
                <th scope="col" className="px-3 py-2 text-left font-medium">
                  Alavancagem
                  <span className="block font-normal">dív. líq. ÷ capital empregado</span>
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  EV/EBITDA
                </th>
                <th scope="col" className="px-3 py-2 text-left font-medium">
                  EBITDA do trimestre
                  <span className="block font-normal">onde cai na faixa da própria empresa</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {linhas.map(({ empresa: e, alav, faixaEbitda }) => (
                <tr key={e.ticker} className="border-t border-border">
                  <th scope="row" className="px-3 py-2 text-left font-medium">
                    {e.ticker}
                    <span className="ml-1.5 text-xs text-muted">{e.pais}</span>
                  </th>
                  <td className="px-3 py-2 text-right tabular-nums">{milhoes(e.fy2025.receita)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{milhoes(e.fy2025.ebitda)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{milhoes(e.fy2025.fcf)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {percentual(e.fy2025.margem_liquida_pct, 2)}
                  </td>
                  <td className="px-3 py-2 text-left">
                    <CelulaAlavancagem a={alav} />
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {multiplo(e.fy2025.derivados.ev_ebitda_x)}
                  </td>
                  <td className="px-3 py-2 text-left">
                    {/* O rotulo do trimestre e DE CADA EMPRESA: no payload elas
                        estao em trimestres diferentes (Q2 e Q3), entao uma
                        coluna rotulada com um trimestre unico mentiria. */}
                    <span className="text-xs text-muted">
                      {trimestreCurto(e.q_recente.trimestre)}
                    </span>{' '}
                    {faixaEbitda === null || faixaEbitda.posicaoPct === null ? (
                      <span className="text-muted">
                        {AUSENTE} <span className="text-xs">(histórico curto)</span>
                      </span>
                    ) : (
                      <span className="tabular-nums">
                        {percentual(faixaEbitda.posicaoPct, 0)} da faixa
                        <span className="ml-1 text-xs text-muted">(n={faixaEbitda.n})</span>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <CardNote className="mt-3">
          <b>Alavancagem.</b> Dívida líquida ÷ (dívida líquida + patrimônio). O patrimônio é
          estimado por lucro ÷ ROE, porque <code>divida_patrimonio_pct</code> do payload usa dívida{' '}
          <b>total</b> e não líquida. Onde o ROE é próximo de zero — a BP em 2025 teve lucro de US$
          55 milhões por itens não recorrentes — a estimativa fica instável e a célula aparece
          vazia, com o motivo, em vez de mostrar um número frágil que parece preciso.
        </CardNote>
        <CardNote className="mt-2">
          <b>Faixa histórica.</b> Posição do EBITDA do último trimestre entre o mínimo e o máximo
          dos trimestres disponíveis <i>da própria empresa</i> — é o que separa nível de momento do
          ciclo. As janelas são irregulares (4 ou 5 trimestres), então o <code>n</code> vem junto;
          comparar a posição entre empresas sem olhar o <code>n</code> compara janelas diferentes.
        </CardNote>
        <CardNote className="mt-2">
          <b>Trimestres diferentes.</b> As empresas divulgam em datas distintas: neste payload há
          companhias em Q2 2026 e outras em Q3 2026. Cada linha mostra o trimestre dela — não existe
          um trimestre único para rotular a coluna.
        </CardNote>
      </Card>
    </div>
  );
}
