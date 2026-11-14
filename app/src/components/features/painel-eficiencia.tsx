import { useMemo, useState, type ReactNode } from 'react';
import { useDados } from '@/hooks/use-dados';
import { Card, CardNote, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { SeletorPeriodo } from '@/components/ui/seletor-periodo';
import { ChartContainer } from '@/components/charts/chart-container';
import { GraficoBarras } from '@/components/charts/grafico-barras';
import { bloco, type Periodo } from '@/types/dashboard-data';
import { decimal, percentual, milhoes, AUSENTE } from '@/lib/formatters';

interface Metrica {
  chave: 'ebitda_por_boe_usd' | 'receita_por_boe_usd' | 'conversao_fcf_pct' | 'capex_fco_pct';
  titulo: string;
  unidade: string;
  formata: (v: number | null) => string;
  nota?: ReactNode;
}

const METRICAS: readonly Metrica[] = [
  {
    chave: 'ebitda_por_boe_usd',
    titulo: 'EBITDA por barril equivalente',
    unidade: 'US$/boe',
    formata: (v) => (v === null ? AUSENTE : decimal(v)),
    nota: 'A leitura mais comparável por barril: normaliza pelo tamanho da operação e sofre menos com a mistura de negócios que a receita.',
  },
  {
    chave: 'receita_por_boe_usd',
    titulo: 'Receita por barril equivalente',
    unidade: 'US$/boe',
    formata: (v) => (v === null ? AUSENTE : decimal(v)),
    nota: (
      <>
        <b>Não é realização de upstream.</b> Exxon, Shell, BP e TotalEnergies têm refino e trading
        dentro da receita, então o indicador fica inflado para as integradas com downstream grande.
        Comparar este número entre uma integrada e a Equinor não é comparar a mesma coisa.
      </>
    ),
  },
  {
    chave: 'conversao_fcf_pct',
    titulo: 'Conversão de EBITDA em caixa livre',
    unidade: '% (FCF ÷ EBITDA)',
    formata: (v) => percentual(v),
  },
  {
    chave: 'capex_fco_pct',
    titulo: 'Intensidade de reinvestimento',
    unidade: '% (capex ÷ fluxo de caixa operacional)',
    formata: (v) => percentual(v),
  },
];

export function PainelEficiencia() {
  const { data, isPending, error } = useDados();
  const [periodo, setPeriodo] = useState<Periodo>('fy2025');

  const comProxy = useMemo(
    () =>
      (data?.empresas ?? [])
        .filter((e) => bloco(e, periodo).derivados.producao_proxy)
        .map((e) => e.ticker),
    [data, periodo],
  );

  /** Producao de outro trimestre: numerador e denominador desencontrados. */
  const comProducaoDefasada = useMemo(
    () =>
      (data?.empresas ?? [])
        .filter((e) => bloco(e, periodo).derivados.producao_defasada)
        .map((e) => {
          const d = bloco(e, periodo).derivados;
          return `${e.ticker} (${d.producao_periodo_do_dado})`;
        }),
    [data, periodo],
  );

  /**
   * Trimestres distintos no payload, lidos do DADO.
   *
   * Estavam escritos a mao aqui ("algumas em Q2 2026 e outras em Q3 2026"). Um
   * rotulo de periodo escrito a mao envelhece sozinho: no dia em que as sete
   * convergirem para o mesmo trimestre, o aviso continuaria afirmando uma
   * divergencia que deixou de existir -- e ninguem receberia um erro por isso.
   */
  const trimestres = useMemo(
    () => [...new Set((data?.empresas ?? []).map((e) => e.q_recente.trimestre))].sort(),
    [data],
  );

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (error || !data) {
    return (
      <Card>
        <CardTitle>Eficiência operacional</CardTitle>
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
          <CardTitle>Eficiência operacional</CardTitle>
          <SeletorPeriodo valor={periodo} onChange={setPeriodo} rotuloTrimestre="trimestre" />
        </div>
        <CardNote className="mt-1">
          Indicadores que normalizam as empresas pelo tamanho da operação — a leitura que separa
          escala de qualidade do barril. Todos são calculados pelo pipeline, não aqui.
        </CardNote>
        {periodo === 'q_recente' && trimestres.length > 1 && (
          <CardNote className="mt-2">
            <b>Atenção ao comparar o trimestre.</b> As empresas divulgam em datas diferentes e o
            payload tem {trimestres.length} trimestres ao mesmo tempo ({trimestres.join(', ')}). O
            seletor diz só &quot;trimestre&quot; porque não existe um único.
          </CardNote>
        )}
        {comProducaoDefasada.length > 0 && (
          <CardNote className="mt-2">
            <b>Produção de outro trimestre em {comProducaoDefasada.join(', ')}.</b> O resultado é do
            trimestre exibido, mas a produção no denominador é a do trimestre indicado — ela não sai
            da demonstração financeira, então o pipeline carrega a anterior até alguém atualizá-la
            pelo relatório da empresa. Enquanto isso durar, receita e EBITDA por barril comparam
            numerador e denominador de períodos diferentes.
          </CardNote>
        )}
        {comProxy.length > 0 && (
          <CardNote className="mt-2">
            <b>Produção por procuração em {comProxy.join(', ')}.</b> A fonte não trouxe a produção
            deste período, então os indicadores por barril usam a produção de outro — o pipeline
            registra isso em <code>producao_proxy</code>, e é por isso que o número existe em vez de
            faltar.
          </CardNote>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {METRICAS.map((m) => {
          const pontos = data.empresas.map((e) => ({
            rotulo: e.ticker,
            valor: bloco(e, periodo).derivados[m.chave],
          }));
          const ausentes = pontos.filter((p) => p.valor === null).map((p) => p.rotulo);
          return (
            <ChartContainer
              key={m.chave}
              titulo={m.titulo}
              unidade={m.unidade}
              descricao={`${m.titulo} por empresa, em ${m.unidade}: ${pontos
                .map((p) => `${p.rotulo} ${m.formata(p.valor)}`)
                .join('; ')}`}
              tabela={{
                colunas: [
                  { chave: 'empresa', rotulo: 'Empresa' },
                  { chave: 'valor', rotulo: m.unidade },
                ],
                linhas: pontos.map((p) => ({ empresa: p.rotulo, valor: m.formata(p.valor) })),
              }}
              nota={
                <>
                  {m.nota}
                  {ausentes.length > 0 && (
                    <>
                      {' '}
                      Sem barra para {ausentes.join(', ')}: o dado está ausente, e barra de altura
                      zero afirmaria um valor.
                    </>
                  )}
                </>
              }
            >
              <GraficoBarras dados={pontos} formata={m.formata} />
            </ChartContainer>
          );
        })}
      </div>

      <Card>
        <CardTitle>Produção</CardTitle>
        <CardNote className="mt-0.5">mil barris de óleo equivalente por dia</CardNote>
        <div className="mt-3">
          <GraficoBarras
            dados={data.empresas.map((e) => ({
              rotulo: e.ticker,
              valor: bloco(e, periodo).derivados.producao_usada_kboed,
            }))}
            formata={(v) => (v === null ? AUSENTE : milhoes(v))}
            altura={200}
          />
        </div>
        <CardNote className="mt-3">
          <b>Shell em duas bases.</b> A empresa publica dois totais de produção: o do grupo (coluna
          anual) e a soma dos segmentos Upstream + Integrated Gas (série trimestral). As duas
          divergem em cerca de 1,5%, então a comparação anual-contra-trimestre dela não é exatamente
          a mesma base.
        </CardNote>
      </Card>
    </div>
  );
}
