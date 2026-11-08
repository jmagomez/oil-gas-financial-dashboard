import { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Ponte } from '@/lib/ponte';
import { milhoes } from '@/lib/formatters';

/**
 * Waterfall sobre BarChart: uma barra INVISIVEL posiciona a base e outra
 * desenha o passo. O Recharts nao tem waterfall nativo, e empilhar um
 * transparente e a forma padrao -- sem canvas, continua tudo em SVG.
 *
 * `isAnimationActive={false}`: a animacao faz o teste de integracao ler
 * barras de altura 0 no primeiro frame, e o ganho visual aqui e nulo.
 */
export function GraficoPonte({ ponte }: { ponte: Ponte }) {
  const dados = useMemo(
    () =>
      ponte.passos.map((p) => {
        if (p.tipo === 'total') {
          return { nome: p.rotulo, base: 0, valor: p.acumulado, tipo: p.tipo, delta: p.delta };
        }
        // Passo de consumo: a barra desce do acumulado anterior ate o atual.
        const topo = p.acumulado - p.delta;
        return {
          nome: p.rotulo,
          base: Math.min(topo, p.acumulado),
          valor: Math.abs(p.delta),
          tipo: p.tipo,
          delta: p.delta,
        };
      }),
    [ponte],
  );

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={dados} margin={{ top: 8, right: 8, left: 8, bottom: 56 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
        <XAxis
          dataKey="nome"
          tick={{ fontSize: 10, fill: 'hsl(var(--muted))' }}
          interval={0}
          angle={-30}
          textAnchor="end"
          height={56}
        />
        <YAxis
          tick={{ fontSize: 10, fill: 'hsl(var(--muted))' }}
          tickFormatter={(v: number) => milhoes(v)}
          width={64}
        />
        <Tooltip
          contentStyle={{
            background: 'hsl(var(--surface))',
            border: '1px solid hsl(var(--border))',
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(_v, _n, item) => {
            const d = item.payload as { delta: number };
            return [`US$ ${milhoes(d.delta)} mi`, 'valor'];
          }}
        />
        <Bar dataKey="base" stackId="p" fill="transparent" isAnimationActive={false} />
        <Bar dataKey="valor" stackId="p" isAnimationActive={false} radius={[2, 2, 0, 0]}>
          {dados.map((d) => (
            <Cell
              key={d.nome}
              fill={d.tipo === 'total' ? 'hsl(var(--accent))' : 'hsl(var(--down))'}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
