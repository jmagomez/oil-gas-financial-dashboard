import type { ReactNode } from 'react';
import { Card, CardNote, CardTitle } from '@/components/ui/card';
import { ChartDataTable, type ColunaTabela } from './chart-data-table';

interface Props {
  titulo: string;
  unidade: string;
  nota?: ReactNode;
  /**
   * Descricao do que o grafico mostra, para leitor de tela. Obrigatoria: o
   * SVG do Recharts e um emaranhado de <path>, e sem isto o usuario de leitor
   * de tela chega num elemento `img` sem rotulo nenhum.
   */
  descricao: string;
  children: ReactNode;
  tabela?: { colunas: readonly ColunaTabela[]; linhas: ReadonlyArray<Record<string, string>> };
}

export function ChartContainer({ titulo, unidade, nota, descricao, children, tabela }: Props) {
  return (
    <Card>
      <CardTitle>{titulo}</CardTitle>
      <CardNote className="mt-0.5">{unidade}</CardNote>
      <div className="mt-3" role="img" aria-label={descricao}>
        {children}
      </div>
      {tabela && (
        <ChartDataTable
          titulo={`${titulo} — ${unidade}`}
          colunas={tabela.colunas}
          linhas={tabela.linhas}
        />
      )}
      {nota && <CardNote className="mt-3">{nota}</CardNote>}
    </Card>
  );
}
