import { describe, expect, it } from 'vitest';
import {
  AUSENTE,
  data,
  decimal,
  milhoes,
  multiplo,
  percentual,
  periodoCurto,
  trimestreCurto,
} from '@/lib/formatters';

describe('formatadores pt-BR', () => {
  it('usa ponto de milhar e virgula decimal', () => {
    expect(milhoes(323910)).toBe('323.910');
    expect(decimal(8.94)).toBe('8,94');
    expect(percentual(9.19, 2)).toBe('9,19%');
    expect(multiplo(17.06)).toBe('17,06×');
  });

  it('ausente vira travessao, nunca zero', () => {
    for (const f of [milhoes, decimal, multiplo]) {
      expect(f(null)).toBe(AUSENTE);
      expect(f(undefined)).toBe(AUSENTE);
    }
    expect(percentual(null)).toBe(AUSENTE);
  });

  it('zero continua sendo zero, nao travessao', () => {
    // A distincao importa: a BP teve lucro perto de zero de verdade.
    expect(milhoes(0)).toBe('0');
    expect(percentual(0)).toBe('0,0%');
  });

  it('descarta infinito e NaN, que seriam resultado de divisao por zero', () => {
    expect(milhoes(Number.POSITIVE_INFINITY)).toBe(AUSENTE);
    expect(decimal(Number.NaN)).toBe(AUSENTE);
  });

  it('negativo mantem o sinal: capex e caixa liquido dependem disso', () => {
    expect(milhoes(-28360)).toBe('-28.360');
  });

  it('os DOIS formatos de periodo do payload sao tratados', () => {
    // historico usa "AAAA-Qn"; q_recente usa "Qn AAAA". Formatos diferentes
    // no mesmo arquivo -- confundir os dois ja seria um bug silencioso.
    expect(periodoCurto('2026-Q1')).toBe('1T26');
    expect(trimestreCurto('Q2 2026')).toBe('2T26');
    expect(periodoCurto('Q2 2026')).toBe('Q2 2026');
    expect(trimestreCurto('2026-Q1')).toBe('2026-Q1');
  });

  it('data nao passa por Date, para o fuso nao deslocar o dia', () => {
    expect(data('2026-11-07')).toBe('07/11/2026');
    expect(data(null)).toBe(AUSENTE);
  });
});
