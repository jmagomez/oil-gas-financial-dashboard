import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';

export interface SerieRadar {
  rotulo: string;
  cor: string;
}

interface Props {
  /** Um objeto por eixo: { eixo: "Solidez", XOM: 42, PBR: 0, ... } */
  dados: ReadonlyArray<Record<string, string | number>>;
  series: readonly SerieRadar[];
}

/**
 * Radar de perfil. Os valores vem JA normalizados 0-100 pelo pipeline -- o app
 * nao recalcula escala.
 *
 * `domain={[0, 100]}` fixo e essencial: com dominio automatico, o eixo se
 * ajustaria aos valores presentes e dois radares com selecoes diferentes de
 * empresas ficariam em escalas diferentes, parecendo comparaveis.
 */
export function GraficoRadar({ dados, series }: Props) {
  return (
    <ResponsiveContainer width="100%" height={340}>
      <RadarChart data={[...dados]} outerRadius="72%">
        <PolarGrid stroke="hsl(var(--border))" />
        <PolarAngleAxis dataKey="eixo" tick={{ fontSize: 10, fill: 'hsl(var(--muted))' }} />
        <PolarRadiusAxis
          domain={[0, 100]}
          tickCount={5}
          tick={{ fontSize: 9, fill: 'hsl(var(--muted))' }}
        />
        {series.map((s) => (
          <Radar
            key={s.rotulo}
            name={s.rotulo}
            dataKey={s.rotulo}
            stroke={s.cor}
            fill={s.cor}
            fillOpacity={0.12}
            isAnimationActive={false}
          />
        ))}
        <Tooltip
          contentStyle={{
            background: 'hsl(var(--surface))',
            border: '1px solid hsl(var(--border))',
            borderRadius: 8,
            fontSize: 12,
          }}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
