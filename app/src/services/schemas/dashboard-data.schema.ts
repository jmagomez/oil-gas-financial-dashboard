import { z } from 'zod';
import {
  anualSchema,
  trimestreSchema,
  mercadoSchema,
  historicoItemSchema,
  referenciaSchema,
  empresaSchema,
} from './indicadores.schema';

/**
 * Contrato do `dashboard_data.json` -- o payload ENRIQUECIDO, gerado por
 * build_dashboard.py.
 *
 * Por que existe um segundo schema: `indicadores_oleo_gas.json` e a fonte
 * curada e tem apenas campos primarios. Os 18 indicadores derivados nascem no
 * pipeline e, desde agora, sao publicados como arquivo. O app consome ESTE,
 * e nao recalcula nenhuma formula -- duas implementacoes da mesma conta
 * divergem, e remover essa duplicacao foi o trabalho desta semana.
 *
 * O schema do primario continua existindo e sendo validado: se o pipeline
 * quebrar o contrato de um dos dois, o deploy falha apontando qual.
 */

const num = z.number().finite().nullable();

/** Campos de PROCEDENCIA: dizem com que numero a conta foi feita. */
const proveniencia = {
  /** "fy" ou "ttm" -- qual base de 12 meses alimentou o indicador. */
  base_12m_ebitda: z.string(),
  base_12m_fcf: z.string(),
  /**
   * Os periodos somados no TTM. MISTURA os dois formatos de rotulo do
   * repositorio ("2025-Q3" do historico e "Q2 2026" do q_recente), porque a
   * janela atravessa os dois. Quem exibir isso precisa dos dois conversores.
   */
  janela_ttm: z.array(z.string()).nullable(),
  /** true quando a producao do periodo veio de outro (caso Equinor FY2025). */
  producao_proxy: z.boolean(),
  producao_usada_kboed: num,
  dias_periodo: z.number().int().positive(),
};

const derivadosPeriodoSchema = z.object({
  ...proveniencia,
  margem_liquida_calc_pct: num,
  margem_ebitda_pct: num,
  nd_ebitda_x: num,
  conversao_fcf_pct: num,
  capex_fco_pct: num,
  receita_por_boe_usd: num,
  ebitda_por_boe_usd: num,
  ev: num,
  ev_por_boed_usd: num,
  fcf_yield_pct: num,
  dividendos_estimados: num,
  cobertura_dividendo_x: num,
});

const derivadosHistoricoSchema = z.object({
  margem_ebitda_pct: num,
  margem_liquida_pct: num,
  conversao_fcf_pct: num,
  capex_fco_pct: num,
  receita_por_boe_usd: num,
  ebitda_por_boe_usd: num,
});

const ttmSchema = z.object({
  receita: num,
  lucro_liquido: num,
  ebitda: num,
  fluxo_caixa_operacional: num,
  fcf: num,
  capex: num,
  producao_kboed: num,
  janela: z.array(z.string()),
});

export const empresaEnriquecidaSchema = z
  .object({
    ticker: z.string().min(1),
    nome: z.string().min(1),
    pais: z.string().min(1),
    fy2025: anualSchema.extend({
      derivados: derivadosPeriodoSchema,
      margem_liquida_fonte_pct: num.optional(),
    }),
    q_recente: trimestreSchema.extend({
      derivados: derivadosPeriodoSchema,
      margem_liquida_fonte_pct: num.optional(),
    }),
    mercado: mercadoSchema,
    historico: z
      .array(historicoItemSchema.extend({ derivados: derivadosHistoricoSchema }))
      .default([]),
    ttm: ttmSchema,
    derivados: z.object({ run_rate_ebitda_pct: num }),
    /** Eixos do radar, normalizados 0-100 pelo pipeline. */
    perfil: z.record(z.string(), z.number().finite()),
    fontes: z.array(z.string().url()).min(1),
    proveniencia: z.record(z.string(), z.unknown()).optional(),
  })
  .superRefine((e, ctx) => {
    // Score fora de 0-100 significa que a normalizacao do radar quebrou. Um
    // eixo com 140 nao e "muito bom": e escala errada, e o grafico sairia
    // fora da area sem nenhum aviso.
    for (const [eixo, v] of Object.entries(e.perfil)) {
      if (v < 0 || v > 100) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `${e.ticker}.perfil.${eixo} = ${v}: fora da escala 0-100`,
        });
      }
    }
  });

export const metaBuildSchema = z.object({
  eixos_perfil: z.array(z.string()).min(1),
  dias_periodo: z.record(z.string(), z.number().int().positive()),
  fator_anualizacao: z.record(z.string(), z.number().positive()),
  tem_historico: z.boolean(),
  empresas_com_ttm: z.number().int().nonnegative(),
  derivados_historico: z.array(z.string()),
});

export const dadosSchema = z
  .object({
    referencia: referenciaSchema,
    empresas: z.array(empresaEnriquecidaSchema).min(1),
    meta_build: metaBuildSchema,
  })
  .superRefine((d, ctx) => {
    // Todo perfil tem de ter exatamente os eixos declarados em meta_build:
    // um eixo a mais numa empresa deforma o radar so dela, silenciosamente.
    const esperados = [...d.meta_build.eixos_perfil].sort().join('|');
    for (const e of d.empresas) {
      const tem = Object.keys(e.perfil).sort().join('|');
      if (tem !== esperados) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `${e.ticker}: eixos do perfil divergem de meta_build.eixos_perfil`,
        });
      }
    }
  });

export type DadosValidados = z.infer<typeof dadosSchema>;
export { empresaSchema };
