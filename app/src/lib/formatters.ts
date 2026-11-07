/**
 * Formatacao pt-BR. Centralizada porque numero financeiro formatado de dois
 * jeitos diferentes na mesma tela parece dois dados diferentes.
 */

const MILHOES = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
const DECIMAL = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Travessao, nao "0" nem "-": ausente nao e zero. */
export const AUSENTE = '—';

/** US$ milhoes, sem casas decimais. */
export function milhoes(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return AUSENTE;
  return MILHOES.format(v);
}

export function decimal(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return AUSENTE;
  return DECIMAL.format(v);
}

export function percentual(v: number | null | undefined, casas = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return AUSENTE;
  const f = new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
  return `${f.format(v)}%`;
}

export function multiplo(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return AUSENTE;
  return `${DECIMAL.format(v)}×`;
}

/**
 * "2026-Q1" -> "1T26". Rotulo curto para eixo de grafico, onde o espaco e
 * escasso e a data completa nao cabe.
 */
export function periodoCurto(periodo: string): string {
  const m = /^(\d{4})-Q([1-4])$/.exec(periodo);
  if (!m) return periodo;
  return `${m[2]}T${m[1]!.slice(2)}`;
}

/** "Q2 2026" -> "2T26". Formato de `q_recente.trimestre`, diferente do acima. */
export function trimestreCurto(trimestre: string): string {
  const m = /^Q([1-4]) (\d{4})$/.exec(trimestre);
  if (!m) return trimestre;
  return `${m[1]}T${m[2]!.slice(2)}`;
}

/** ISO para dd/mm/aaaa, sem passar por Date (que desloca por fuso). */
export function data(iso: string | null | undefined): string {
  if (!iso) return AUSENTE;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return iso;
  return `${m[3]}/${m[2]}/${m[1]}`;
}
