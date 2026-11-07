import type { Alavancagem } from '@/lib/derivacoes';
import { milhoes, percentual, AUSENTE } from '@/lib/formatters';

/**
 * A uniao discriminada de `alavancagem()` chega aqui e o componente e obrigado
 * a tratar os tres casos -- e isso que impede caixa liquido de ser desenhado
 * como alavancagem negativa.
 */
export function CelulaAlavancagem({ a }: { a: Alavancagem }) {
  switch (a.tipo) {
    case 'gearing':
      return <span className="tabular-nums">{percentual(a.pct)}</span>;
    case 'caixa_liquido':
      return (
        <span className="text-up">
          caixa líquido
          <span className="ml-1 tabular-nums text-muted">US$ {milhoes(a.caixaLiquido)} mi</span>
        </span>
      );
    case 'indisponivel':
      return (
        <span className="text-muted" title={a.motivo}>
          {AUSENTE}
          <span className="ml-1 text-xs">({a.motivo})</span>
        </span>
      );
  }
}
