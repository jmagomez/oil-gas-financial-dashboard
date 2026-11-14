import { z } from 'zod';

/**
 * Validacao do contrato na FRONTEIRA.
 *
 * O produtor e um pipeline Python curado a mao que evolui em outro ritmo que
 * este app. Sem validacao, um campo renomeado la vira `undefined` aqui e vaza
 * silencioso ate um grafico vazio tres camadas adiante. Com Zod a falha e
 * imediata e diz qual campo, em qual empresa.
 *
 * As regras com `superRefine` abaixo nao sao decorativas: cada uma corresponde
 * a uma inconsistencia real ja observada no payload.
 */

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
/** "Q2 2026" -- o rotulo usado em `q_recente`. */
const TRIMESTRE = /^Q[1-4] \d{4}$/;
/** "2026-Q1" -- o rotulo usado em `historico`. Formato DIFERENTE, de proposito. */
const PERIODO_HIST = /^\d{4}-Q[1-4]$/;

/** Campo monetario/percentual: pode ser ausente, e ausente NAO e zero. */
const num = z.number().finite().nullable();

const blocoBase = {
  receita: num,
  lucro_liquido: num,
  ebitda: num,
  margem_liquida_pct: num,
  fluxo_caixa_operacional: num,
  fcf: num,
  capex: num,
  divida_liquida: num,
  divida_patrimonio_pct: num,
  roe_pct: num,
  roa_pct: num,
  // Ausente para a Equinor em FY2025 (a fonte padronizada nao tinha o numero
  // de forma consistente). Onde falta, indicador por boe fica ausente.
  producao_kboed: num,
};

export const anualSchema = z.object(blocoBase);

export const trimestreSchema = z.object({
  ...blocoBase,
  trimestre: z.string().regex(TRIMESTRE, 'trimestre deve ser "Q<n> AAAA"'),
});

export const mercadoSchema = z.object({
  market_cap: num,
  pe: num,
  dividend_yield_pct: num,
  preco_acao: num,
});

export const historicoItemSchema = z.object({
  periodo: z.string().regex(PERIODO_HIST, 'periodo deve ser "AAAA-Q<n>"'),
  receita: num,
  lucro_liquido: num,
  ebitda: num,
  fluxo_caixa_operacional: num,
  fcf: num,
  capex: num,
  divida_liquida: num,
  producao_kboed: num,
});

export const empresaSchema = z
  .object({
    ticker: z.string().min(1),
    nome: z.string().min(1),
    pais: z.string().min(1),
    fy2025: anualSchema,
    q_recente: trimestreSchema,
    mercado: mercadoSchema,
    historico: z.array(historicoItemSchema).default([]),
    fontes: z.array(z.string().url()).min(1, 'empresa sem fonte citada'),
    proveniencia: z.record(z.string(), z.unknown()).optional(),
  })
  .superRefine((e, ctx) => {
    // Capex e saida de caixa: no payload ele e NEGATIVO. Um capex positivo
    // significa sinal invertido na coleta, e inverteria a intensidade de
    // reinvestimento sem nenhum sinal visivel na tela.
    for (const [bloco, v] of [
      ['fy2025', e.fy2025.capex],
      ['q_recente', e.q_recente.capex],
    ] as const) {
      if (v !== null && v > 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `${e.ticker}.${bloco}.capex = ${v}: capex deve ser negativo (saida de caixa)`,
        });
      }
    }
    // O historico nao pode conter o proprio q_recente: o pipeline move o
    // trimestre para o historico QUANDO um novo entra, e ter os dois seria
    // contar o mesmo periodo duas vezes em qualquer soma TTM.
    const [q, ano] = e.q_recente.trimestre.split(' ');
    const rotuloEquivalente = `${ano}-${q}`;
    if (e.historico.some((h) => h.periodo === rotuloEquivalente)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `${e.ticker}: ${rotuloEquivalente} esta em historico E em q_recente`,
      });
    }
    // Historico ordenado e sem periodo repetido -- qualquer serie desenhada
    // daqui assume ordem cronologica.
    const periodos = e.historico.map((h) => h.periodo);
    if (new Set(periodos).size !== periodos.length) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `${e.ticker}: historico com periodo repetido`,
      });
    }
    if ([...periodos].sort().join() !== periodos.join()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `${e.ticker}: historico fora de ordem cronologica`,
      });
    }
  });

export const referenciaSchema = z.object({
  data_consulta: z.string().regex(ISO_DATE),
  moeda: z.string().min(1),
  periodo_anual: z.string().min(1),
  // DELIBERADAMENTE sem validacao cruzada contra q_recente.trimestre: no
  // payload real este rotulo diz "Q3 2026" enquanto XOM, CVX e PBR estao em
  // "Q2 2026". As empresas divulgam em datas diferentes, entao NAO existe um
  // trimestre global -- e a tela usa o rotulo de cada empresa, nunca este.
  periodo_trimestral: z.string().min(1),
  fonte_principal: z.string().min(1),
  notas: z.array(z.string()),
  versao_dados: z.string().min(1),
  atualizado_em: z.string().regex(ISO_DATE),
  schema_historico: z.string().optional(),
});

export const payloadSchema = z
  .object({
    referencia: referenciaSchema,
    empresas: z.array(empresaSchema).min(1, 'payload sem empresas'),
  })
  .superRefine((p, ctx) => {
    const tickers = p.empresas.map((e) => e.ticker);
    if (new Set(tickers).size !== tickers.length) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'ticker repetido em empresas' });
    }
  });

export type PayloadValidado = z.infer<typeof payloadSchema>;
