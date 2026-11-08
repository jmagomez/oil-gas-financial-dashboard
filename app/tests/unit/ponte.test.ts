import { describe, expect, it } from 'vitest';
import { montaPonte, LIMIAR_RESIDUO_REL } from '@/lib/ponte';
import { dadosSchema } from '@/services/schemas/dashboard-data.schema';
import dadosReais from '../fixtures/dashboard-data.json';

const d = dadosSchema.parse(dadosReais);
const emp = (t: string) => d.empresas.find((e) => e.ticker === t)!;

describe('montaPonte', () => {
  it('encadeia receita -> EBITDA -> FCO -> FCF com os valores do periodo', () => {
    const b = emp('XOM').fy2025;
    const p = montaPonte(b)!;
    const acum = Object.fromEntries(p.passos.map((s) => [s.rotulo, s.acumulado]));
    expect(acum['Receita']).toBe(b.receita);
    expect(acum['EBITDA']).toBe(b.ebitda);
    expect(acum['Fluxo de caixa operacional']).toBe(b.fluxo_caixa_operacional);
    expect(acum['Free cash flow']).toBe(b.fcf);
  });

  it('os passos de consumo sao NEGATIVOS e somam a diferenca', () => {
    const b = emp('XOM').fy2025;
    const p = montaPonte(b)!;
    const custos = p.passos.find((s) => s.rotulo === 'Custos operacionais')!;
    const giro = p.passos.find((s) => s.rotulo.startsWith('Capital de giro'))!;
    expect(custos.delta).toBe(b.ebitda! - b.receita!);
    expect(custos.delta).toBeLessThan(0);
    expect(giro.delta).toBe(b.fluxo_caixa_operacional! - b.ebitda!);
    // Capex ja vem negativo do payload; a ponte nao inverte sinal.
    expect(p.passos.find((s) => s.rotulo === 'Capex')!.delta).toBe(b.capex);
  });

  it('a ponte da XOM fecha exatamente: residuo zero', () => {
    const p = montaPonte(emp('XOM').fy2025)!;
    expect(p.residuo).toBe(0);
    expect(p.residuoRelevante).toBe(false);
  });

  it('a da SHELL NAO fecha, e o residuo e exposto em vez de escondido', () => {
    // No payload real: FCO 42.863, capex -18.948 -> 23.915, mas o FCF
    // publicado e 23.916. Um dolar, por arredondamento na fonte. Forcar as
    // barras a fechar esconderia a diferenca.
    const b = emp('SHEL').fy2025;
    const p = montaPonte(b)!;
    expect(b.fluxo_caixa_operacional! + b.capex!).not.toBe(b.fcf);
    expect(p.residuo).toBe(1);
    // Um dolar em 23.916 nao chega perto do limiar: e arredondamento.
    expect(p.residuoRelevante).toBe(false);
    expect(Math.abs(p.residuo) / Math.abs(b.fcf!)).toBeLessThan(LIMIAR_RESIDUO_REL);
  });

  it('marca residuo RELEVANTE quando passa de 1% do FCF', () => {
    const b = { ...emp('XOM').fy2025, fcf: emp('XOM').fy2025.fcf! + 5000 };
    const p = montaPonte(b)!;
    expect(p.residuo).toBe(5000);
    expect(p.residuoRelevante).toBe(true);
  });

  it('e null quando falta qualquer campo da cadeia, em vez de somar buraco', () => {
    for (const campo of ['receita', 'ebitda', 'fluxo_caixa_operacional', 'capex', 'fcf'] as const) {
      expect(montaPonte({ ...emp('XOM').fy2025, [campo]: null })).toBeNull();
    }
  });
});
