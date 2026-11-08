import type { BlocoEnriquecido } from '@/types/dashboard-data';

/**
 * Ponte de caixa: da receita ao caixa livre, passo a passo.
 *
 * Os passos saem de subtracoes entre campos do MESMO periodo -- nada aqui e
 * estimado:
 *
 *   receita
 *   - (receita - ebitda)     custos operacionais
 *   = ebitda
 *   - (ebitda - fco)         capital de giro, impostos e juros, juntos
 *   = fco
 *   + capex                  (negativo no payload)
 *   = fcf
 *
 * Por que "juntos": o payload nao abre capital de giro, imposto e juro em
 * campos separados, e inventar a abertura seria afirmar numeros que a fonte
 * nao tem. O passo e rotulado pelo que ele e -- um agregado.
 */
export interface PassoPonte {
  rotulo: string;
  /** Valor do passo. Negativo = consome caixa. */
  delta: number;
  /** Acumulado APOS o passo, para posicionar a barra flutuante. */
  acumulado: number;
  tipo: 'total' | 'consumo';
  nota?: string | undefined;
}

export interface Ponte {
  passos: PassoPonte[];
  /**
   * fcf - (fco + capex). Deveria ser zero.
   *
   * NAO e sempre: no payload real a Shell em FY2025 tem fco 42.863, capex
   * -18.948 e fcf 23.916 -- um dolar de diferenca, por arredondamento na
   * fonte. Forcar as barras a fechar esconderia isso; mostrar o residuo
   * mantem a soma honesta. Os outros 13 casos fecham exato.
   */
  residuo: number;
  /** Acima disto o residuo deixa de ser arredondamento e merece destaque. */
  residuoRelevante: boolean;
}

/** US$ milhoes. Acima de 1% do FCF, o residuo nao e arredondamento. */
export const LIMIAR_RESIDUO_REL = 0.01;

export function montaPonte(b: BlocoEnriquecido): Ponte | null {
  const { receita, ebitda, fluxo_caixa_operacional: fco, capex, fcf } = b;
  if (receita === null || ebitda === null || fco === null || capex === null || fcf === null) {
    return null;
  }

  const passos: PassoPonte[] = [
    { rotulo: 'Receita', delta: receita, acumulado: receita, tipo: 'total' },
    {
      rotulo: 'Custos operacionais',
      delta: ebitda - receita,
      acumulado: ebitda,
      tipo: 'consumo',
      nota: 'tudo que separa receita de EBITDA',
    },
    { rotulo: 'EBITDA', delta: ebitda, acumulado: ebitda, tipo: 'total' },
    {
      rotulo: 'Capital de giro, impostos e juros',
      delta: fco - ebitda,
      acumulado: fco,
      tipo: 'consumo',
      nota: 'agregado: a fonte não abre os três separadamente',
    },
    { rotulo: 'Fluxo de caixa operacional', delta: fco, acumulado: fco, tipo: 'total' },
    { rotulo: 'Capex', delta: capex, acumulado: fco + capex, tipo: 'consumo' },
    { rotulo: 'Free cash flow', delta: fcf, acumulado: fcf, tipo: 'total' },
  ];

  const residuo = fcf - (fco + capex);
  const base = Math.abs(fcf) || 1;
  return { passos, residuo, residuoRelevante: Math.abs(residuo) / base > LIMIAR_RESIDUO_REL };
}
