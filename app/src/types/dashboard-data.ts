/**
 * Contrato do `dashboard_data.json`: o payload enriquecido.
 *
 * Tipos derivados do schema Zod com `z.infer`, e nao escritos a mao como em
 * `types/indicadores.ts`. A diferenca e deliberada: ali as interfaces existem
 * para DOCUMENTAR a fonte curada, e o guard de divergencia paga o custo de
 * manter duas descricoes. Aqui a forma e consequencia mecanica do que o
 * pipeline gera -- manter uma copia a mao so criaria um lugar para divergir
 * sem nenhum ganho de leitura.
 */
import type { z } from 'zod';
import type {
  dadosSchema,
  empresaEnriquecidaSchema,
  metaBuildSchema,
} from '@/services/schemas/dashboard-data.schema';

export type Dados = z.infer<typeof dadosSchema>;
export type EmpresaEnriquecida = z.infer<typeof empresaEnriquecidaSchema>;
export type MetaBuild = z.infer<typeof metaBuildSchema>;

export type BlocoEnriquecido = EmpresaEnriquecida['anual'] | EmpresaEnriquecida['q_recente'];
export type DerivadosPeriodo = EmpresaEnriquecida['anual']['derivados'];
export type HistoricoEnriquecido = EmpresaEnriquecida['historico'][number];

/** Qual coluna de periodo a tela esta mostrando. */
export type Periodo = 'anual' | 'q_recente';

export function bloco(e: EmpresaEnriquecida, p: Periodo): BlocoEnriquecido {
  return p === 'anual' ? e.anual : e.q_recente;
}

/**
 * Rotulo do periodo, sempre de CADA EMPRESA: no payload elas podem estar em
 * trimestres (e, na virada, em anos fiscais) diferentes, e um rotulo global
 * mentiria.
 */
export function rotuloPeriodo(e: EmpresaEnriquecida, p: Periodo): string {
  return p === 'anual' ? `FY${e.anual.ano}` : e.q_recente.trimestre;
}
