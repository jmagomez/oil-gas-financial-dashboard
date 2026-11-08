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

export interface PontoBarra {
  rotulo: string;
  valor: number | null;
  destacado?: boolean;
}

interface Props {
  dados: readonly PontoBarra[];
  formata: (v: number | null) => string;
  altura?: number;
}

/**
 * Comparativo entre empresas. Barras ausentes sao PULADAS, nao desenhadas
 * como zero -- a Equinor sem producao em FY2025 nao tem barra por boe, e uma
 * barra de altura zero afirmaria "produziu nada".
 */
export function GraficoBarras({ dados, formata, altura = 240 }: Props) {
  const presentes = dados.filter((d): d is PontoBarra & { valor: number } => d.valor !== null);

  return (
    <ResponsiveContainer width="100%" height={altura}>
      <BarChart data={presentes} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
        <XAxis dataKey="rotulo" tick={{ fontSize: 11, fill: 'hsl(var(--muted))' }} interval={0} />
        <YAxis
          tick={{ fontSize: 10, fill: 'hsl(var(--muted))' }}
          tickFormatter={(v: number) => formata(v)}
          width={64}
        />
        <Tooltip
          contentStyle={{
            background: 'hsl(var(--surface))',
            border: '1px solid hsl(var(--border))',
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(v) => formata(Number(v))}
        />
        <Bar dataKey="valor" isAnimationActive={false} radius={[2, 2, 0, 0]}>
          {presentes.map((d) => (
            <Cell key={d.rotulo} fill={d.destacado ? 'hsl(var(--accent))' : 'hsl(var(--muted))'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
