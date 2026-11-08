import {
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';

export interface PontoDispersao {
  rotulo: string;
  x: number;
  y: number;
  /** Area da bolha. Opcional -- sem ela o grafico e dispersao simples. */
  z?: number | undefined;
}

interface Props {
  dados: readonly PontoDispersao[];
  rotuloX: string;
  rotuloY: string;
  formataX: (v: number) => string;
  formataY: (v: number) => string;
}

/**
 * Dispersao com rotulo em cada ponto.
 *
 * O rotulo fica NO ponto, nao numa legenda: com sete empresas, legenda por cor
 * obriga o leitor a ir e voltar, e cor sozinha nao serve a quem nao distingue
 * matiz (WCAG 1.4.1). Aqui o ticker esta escrito ao lado do ponto.
 */
export function GraficoDispersao({ dados, rotuloX, rotuloY, formataX, formataY }: Props) {
  const temZ = dados.some((d) => d.z !== undefined);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ScatterChart margin={{ top: 12, right: 24, left: 8, bottom: 32 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          type="number"
          dataKey="x"
          name={rotuloX}
          tick={{ fontSize: 10, fill: 'hsl(var(--muted))' }}
          tickFormatter={formataX}
          label={{
            value: rotuloX,
            position: 'insideBottom',
            offset: -20,
            style: { fontSize: 11, fill: 'hsl(var(--muted))' },
          }}
        />
        <YAxis
          type="number"
          dataKey="y"
          name={rotuloY}
          tick={{ fontSize: 10, fill: 'hsl(var(--muted))' }}
          tickFormatter={formataY}
          width={64}
          label={{
            value: rotuloY,
            angle: -90,
            position: 'insideLeft',
            style: { fontSize: 11, fill: 'hsl(var(--muted))' },
          }}
        />
        {temZ && <ZAxis type="number" dataKey="z" range={[60, 600]} />}
        <Tooltip
          contentStyle={{
            background: 'hsl(var(--surface))',
            border: '1px solid hsl(var(--border))',
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(v, n) => [n === 'x' ? formataX(Number(v)) : formataY(Number(v)), String(n)]}
        />
        <Scatter data={[...dados]} fill="hsl(var(--accent))" isAnimationActive={false}>
          <LabelList
            dataKey="rotulo"
            position="top"
            style={{ fontSize: 10, fill: 'hsl(var(--fg))' }}
          />
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  );
}
