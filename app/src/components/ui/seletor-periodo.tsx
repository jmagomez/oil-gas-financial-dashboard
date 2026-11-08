import * as ToggleGroup from '@radix-ui/react-toggle-group';
import type { Periodo } from '@/types/dashboard-data';
import { cn } from '@/lib/cn';

interface Props {
  valor: Periodo;
  onChange: (p: Periodo) => void;
  /**
   * Rotulo do trimestre. Vem de uma empresa especifica quando ha uma
   * selecionada; quando a tela compara todas, fica "trimestre" sem numero,
   * porque as empresas estao em trimestres diferentes.
   */
  rotuloTrimestre: string;
}

export function SeletorPeriodo({ valor, onChange, rotuloTrimestre }: Props) {
  return (
    <ToggleGroup.Root
      type="single"
      value={valor}
      onValueChange={(v) => {
        // O Radix emite "" quando o item ativo e clicado de novo. Ignorar
        // mantem sempre um periodo escolhido: nao existe "nenhum periodo".
        if (v === 'fy2025' || v === 'q_recente') onChange(v);
      }}
      aria-label="Período"
      className="inline-flex rounded-lg border border-border p-0.5"
    >
      {(
        [
          ['fy2025', 'FY2025'],
          ['q_recente', rotuloTrimestre],
        ] as const
      ).map(([v, rot]) => (
        <ToggleGroup.Item
          key={v}
          value={v}
          className={cn(
            'rounded-md px-3 py-1 text-xs font-medium text-muted transition-colors',
            'hover:text-fg',
            // Estado ativo marcado por fundo E peso, nao so por cor.
            'data-[state=on]:bg-accent data-[state=on]:font-semibold data-[state=on]:text-bg',
          )}
        >
          {rot}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
