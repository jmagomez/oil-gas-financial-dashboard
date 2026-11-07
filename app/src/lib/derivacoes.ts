import type { BlocoFinanceiro, HistoricoItem, Valor } from '@/types/indicadores';

/**
 * Derivacoes de LEITURA, nao de negocio.
 *
 * Indicador de negocio continua sendo calculado por build_dashboard.py -- o
 * pipeline e o unico ponto que deriva, e duas implementacoes da mesma formula
 * divergem. O que mora aqui e o que ajuda a LER um valor: situa-lo na faixa
 * historica da propria empresa, decidir se ha pontos suficientes para desenhar
 * linha, e dizer quando uma estimativa nao e confiavel.
 */

/* ==========================================================================
   Patrimonio estimado, e por que ele vem com um aviso
   ========================================================================== */

/**
 * Abaixo deste ROE (em modulo) a estimativa de patrimonio e descartada.
 *
 * Medido no payload real, FY2025:
 *   XOM  lucro 29.760, ROE 11,1%  -> patrimonio 268.108
 *        ROE variando +-0,02 p.p. move o resultado em 0,4%
 *   BP   lucro 55,     ROE 0,1%   -> patrimonio 55.000
 *        ROE variando +-0,02 p.p. move o resultado em 41,7%
 *
 * O lucro da BP em FY2025 foi de US$ 55 milhoes por itens nao-recorrentes
 * (o proprio payload registra isso em `referencia.notas`). Dividir quase-zero
 * por quase-zero amplifica o arredondamento do ROE a ponto de o resultado
 * nao significar nada -- e o ruim e que ele PARECE um numero preciso.
 */
export const LIMIAR_ROE_CONFIAVEL_PCT = 1;

/**
 * Patrimonio liquido, estimado a partir de lucro / ROE.
 *
 * Nao sai de `divida_patrimonio_pct`: conferido contra os dados, esse campo
 * usa divida TOTAL e nao liquida (XOM daria 201.595 por esse caminho, contra
 * 268.108 via ROE, que e o valor real).
 *
 * Devolve `null` quando a conta nao e confiavel, em vez de um numero frágil.
 */
export function patrimonioEstimado(b: BlocoFinanceiro): number | null {
  const { lucro_liquido: lucro, roe_pct: roe } = b;
  if (lucro === null || roe === null) return null;
  if (Math.abs(roe) < LIMIAR_ROE_CONFIAVEL_PCT) return null;
  return lucro / (roe / 100);
}

/* ==========================================================================
   Alavancagem
   ========================================================================== */

/**
 * Uniao discriminada de proposito: caixa liquido NAO e alavancagem negativa.
 *
 * Equinor e TotalEnergies estao em caixa liquido (divida liquida de -11.888 e
 * -31.499 em FY2025). Um grafico que coloca -40% ao lado dos +46% da Petrobras
 * na mesma escala afirma uma comparacao que nao existe. Com esta uniao, a tela
 * nao CONSEGUE plotar caixa liquido como barra negativa sem tratar o caso.
 */
export type Alavancagem =
  | { tipo: 'gearing'; pct: number }
  | { tipo: 'caixa_liquido'; caixaLiquido: number }
  | { tipo: 'indisponivel'; motivo: string };

export function alavancagem(b: BlocoFinanceiro): Alavancagem {
  const nd = b.divida_liquida;
  if (nd === null) return { tipo: 'indisponivel', motivo: 'dívida líquida ausente' };
  if (nd < 0) return { tipo: 'caixa_liquido', caixaLiquido: -nd };

  const pl = patrimonioEstimado(b);
  if (pl === null) {
    return {
      tipo: 'indisponivel',
      motivo:
        b.roe_pct !== null && Math.abs(b.roe_pct) < LIMIAR_ROE_CONFIAVEL_PCT
          ? `ROE de ${b.roe_pct}% é baixo demais para estimar patrimônio`
          : 'patrimônio não estimável',
    };
  }
  const ce = pl + nd;
  if (ce <= 0) return { tipo: 'indisponivel', motivo: 'capital empregado não positivo' };
  return { tipo: 'gearing', pct: (nd / ce) * 100 };
}

/* ==========================================================================
   Leitura ciclica: onde o valor de hoje cai na faixa da propria empresa
   ========================================================================== */

/** Minimo de pontos para que "faixa" signifique algo. Dois pontos nao e faixa. */
export const MIN_PONTOS_FAIXA = 3;

export interface FaixaHistorica {
  min: number;
  max: number;
  /** 0 = no fundo da faixa, 100 = no topo. `null` se min === max. */
  posicaoPct: number | null;
  n: number;
}

/**
 * Situa `atual` dentro da faixa observada na propria empresa.
 *
 * E o acrescimo de maior valor do dashboard e nao precisa de dado novo:
 * margem EBITDA de 25% nao diz nada sozinha num setor ciclico, mas diz muito
 * ao lado de "e o topo da faixa dos ultimos N trimestres DESTA empresa".
 *
 * Comparar a posicao entre empresas exige cuidado: as janelas sao irregulares
 * (4 ou 5 trimestres, dependendo da empresa), entao `n` acompanha o resultado.
 */
export function faixaHistorica(valores: readonly Valor[], atual: Valor): FaixaHistorica | null {
  const nums = valores.filter((v): v is number => v !== null);
  if (nums.length < MIN_PONTOS_FAIXA || atual === null) return null;

  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const posicaoPct = max === min ? null : ((atual - min) / (max - min)) * 100;
  return { min, max, posicaoPct, n: nums.length };
}

/** Extrai um campo do historico na ordem em que ele aparece. */
export function serieDoHistorico(
  historico: readonly HistoricoItem[],
  campo: keyof Omit<HistoricoItem, 'periodo'>,
): Valor[] {
  return historico.map((h) => h[campo]);
}

/**
 * Se vale desenhar linha. Abaixo de MIN_PONTOS_FAIXA a tela mostra o nivel e
 * NAO desenha tendencia -- serie de 2 pontos nao e tendencia, e uma reta
 * entre dois pontos sugere direcao que o dado nao sustenta.
 */
export function temTendencia(valores: readonly Valor[]): boolean {
  return valores.filter((v) => v !== null).length >= MIN_PONTOS_FAIXA;
}
