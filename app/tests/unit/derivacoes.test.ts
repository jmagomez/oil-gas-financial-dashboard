import { describe, expect, it } from 'vitest';
import {
  alavancagem,
  faixaHistorica,
  patrimonioEstimado,
  serieDoHistorico,
  temTendencia,
  LIMIAR_ROE_CONFIAVEL_PCT,
} from '@/lib/derivacoes';
import { payloadSchema } from '@/services/schemas/indicadores.schema';
import payloadReal from '../fixtures/payload.json';

const p = payloadSchema.parse(payloadReal);
const emp = (t: string) => p.empresas.find((e) => e.ticker === t)!;

describe('patrimonioEstimado', () => {
  it('sai do ROE e nao do D/E, porque D/E usa divida total', () => {
    const xom = emp('XOM').fy2025;
    // lucro 29.760 / ROE 11,1% = 268.108, que e o patrimonio real.
    // Pelo D/E (32.860 / 16,3%) daria 201.595 -- errado.
    expect(patrimonioEstimado(xom)).toBeCloseTo(268108, -2);
    const viaDE = xom.divida_liquida! / (xom.divida_patrimonio_pct! / 100);
    expect(Math.abs(viaDE - 268108)).toBeGreaterThan(50000);
  });

  it('DESCARTA a estimativa quando o ROE e baixo demais (caso BP)', () => {
    // BP FY2025: lucro de US$ 55 mi por itens nao-recorrentes, ROE 0,1%.
    // Dividir quase-zero por quase-zero da um numero que PARECE preciso:
    // +-0,02 p.p. no ROE move o resultado em ~42%.
    const bp = emp('BP').fy2025;
    expect(bp.roe_pct).toBeLessThan(LIMIAR_ROE_CONFIAVEL_PCT);
    expect(patrimonioEstimado(bp)).toBeNull();
  });

  it('e null quando falta lucro ou ROE', () => {
    const base = emp('XOM').fy2025;
    expect(patrimonioEstimado({ ...base, roe_pct: null })).toBeNull();
    expect(patrimonioEstimado({ ...base, lucro_liquido: null })).toBeNull();
  });
});

describe('alavancagem', () => {
  it('devolve gearing para quem tem divida liquida positiva', () => {
    const a = alavancagem(emp('XOM').fy2025);
    expect(a.tipo).toBe('gearing');
    if (a.tipo === 'gearing') expect(a.pct).toBeCloseTo(10.9, 1);
  });

  it('caixa liquido NAO vira gearing negativo (caso Equinor)', () => {
    // ND de -11.888: um grafico que plota isso como -40% ao lado de +46% da
    // Petrobras afirma uma comparacao que nao existe.
    const a = alavancagem(emp('EQNR').fy2025);
    expect(a.tipo).toBe('caixa_liquido');
    if (a.tipo === 'caixa_liquido') expect(a.caixaLiquido).toBe(11888);
  });

  it('fica indisponivel, com motivo, quando o patrimonio nao e estimavel', () => {
    const a = alavancagem(emp('BP').fy2025);
    expect(a.tipo).toBe('indisponivel');
    if (a.tipo === 'indisponivel') expect(a.motivo).toMatch(/ROE/);
  });

  it('fica indisponivel quando a divida liquida esta ausente', () => {
    const a = alavancagem({ ...emp('XOM').fy2025, divida_liquida: null });
    expect(a.tipo).toBe('indisponivel');
  });
});

describe('faixaHistorica', () => {
  it('situa o valor atual entre o minimo e o maximo da propria empresa', () => {
    const f = faixaHistorica([10, 20, 30, 40], 30);
    expect(f).not.toBeNull();
    expect(f!.min).toBe(10);
    expect(f!.max).toBe(40);
    expect(f!.posicaoPct).toBeCloseTo(66.7, 1);
    expect(f!.n).toBe(4);
  });

  it('ignora ausentes na faixa, mas conta so os presentes em n', () => {
    const f = faixaHistorica([10, null, 30, 40], 40);
    expect(f!.n).toBe(3);
    expect(f!.posicaoPct).toBe(100);
  });

  it('e null com menos de 3 pontos: duas observacoes nao sao faixa', () => {
    expect(faixaHistorica([10, 20], 15)).toBeNull();
  });

  it('posicao e null quando a faixa e degenerada (min === max)', () => {
    const f = faixaHistorica([5, 5, 5], 5);
    expect(f!.posicaoPct).toBeNull();
  });

  it('funciona sobre o historico real, com a janela de cada empresa', () => {
    const xom = emp('XOM');
    const serie = serieDoHistorico(xom.historico, 'ebitda');
    const f = faixaHistorica(serie, xom.q_recente.ebitda);
    expect(f).not.toBeNull();
    // A janela e irregular entre empresas (4 ou 5), entao n acompanha.
    expect(f!.n).toBe(xom.historico.length);
  });
});

describe('temTendencia', () => {
  it('exige 3 pontos: reta entre 2 sugere direcao que o dado nao sustenta', () => {
    expect(temTendencia([1, 2])).toBe(false);
    expect(temTendencia([1, 2, 3])).toBe(true);
    expect(temTendencia([1, null, 3])).toBe(false);
  });
});
