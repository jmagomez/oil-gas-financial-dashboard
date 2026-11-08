/**
 * Contrato publicado pelo pipeline Python em indicadores_oleo_gas.json.
 *
 * Os nomes seguem o payload em snake_case de proposito. Converter para
 * camelCase exigiria uma camada de mapeamento entre a fronteira (Zod) e o
 * dominio -- mais um lugar para divergir do produtor.
 */

/** Campo do payload: `null` significa AUSENTE, nunca zero. */
export type Valor = number | null;

export interface BlocoFinanceiro {
  receita: Valor;
  lucro_liquido: Valor;
  ebitda: Valor;
  margem_liquida_pct: Valor;
  fluxo_caixa_operacional: Valor;
  fcf: Valor;
  /** NEGATIVO no payload: e saida de caixa. */
  capex: Valor;
  /** Negativo = CAIXA LIQUIDO. Ver `alavancagem()` em lib/derivacoes. */
  divida_liquida: Valor;
  /** Usa divida TOTAL, nao liquida -- conferido contra os dados. */
  divida_patrimonio_pct: Valor;
  roe_pct: Valor;
  roa_pct: Valor;
  /** Ausente para a Equinor em FY2025. */
  producao_kboed: Valor;
}

/** O bloco anual nao tem campo proprio: e um alias, nao uma extensao vazia. */
export type BlocoAnual = BlocoFinanceiro;

export interface BlocoTrimestral extends BlocoFinanceiro {
  /** "Q2 2026". Varia POR EMPRESA -- nao existe trimestre global no payload. */
  trimestre: string;
}

export interface Mercado {
  market_cap: Valor;
  pe: Valor;
  /**
   * Para a Petrobras o proprio payload avisa que o numero e uma FAIXA de
   * referencia (~5% a ~9%), nao um valor preciso: as fontes divergem por
   * metodologia (forward vs trailing, PBR vs PBR.A) e pela politica de
   * proventos extraordinarios. Ranquear por este campo sem a ressalva produz
   * conclusao errada com numero certo.
   */
  dividend_yield_pct: Valor;
  preco_acao: Valor;
}

/** Item de `historico`. Rotulo "AAAA-Q<n>" -- formato diferente de `trimestre`. */
export interface HistoricoItem {
  periodo: string;
  receita: Valor;
  lucro_liquido: Valor;
  ebitda: Valor;
  fluxo_caixa_operacional: Valor;
  fcf: Valor;
  capex: Valor;
  divida_liquida: Valor;
  producao_kboed: Valor;
}

export interface Empresa {
  ticker: string;
  nome: string;
  pais: string;
  fy2025: BlocoAnual;
  q_recente: BlocoTrimestral;
  mercado: Mercado;
  historico: HistoricoItem[];
  fontes: string[];
  proveniencia?: Record<string, unknown> | undefined;
}

export interface Referencia {
  data_consulta: string;
  moeda: string;
  periodo_anual: string;
  /** Rotulo global que NAO bate com todas as empresas. A tela nao o usa. */
  periodo_trimestral: string;
  fonte_principal: string;
  notas: string[];
  versao_dados: string;
  atualizado_em: string;
  schema_historico?: string | undefined;
}

export interface Payload {
  referencia: Referencia;
  empresas: Empresa[];
}

/* --------------------------------------------------------------------------
   Guard de divergencia, em tempo de COMPILACAO.

   As interfaces acima existem para serem lidas; os schemas Zod existem para
   validar. Nada impedia os dois de divergirem em silencio. As linhas abaixo
   nao geram codigo: se schema e interface deixarem de descrever a mesma
   forma, `tsc` falha e nomeia o campo.
   -------------------------------------------------------------------------- */
import type { z } from 'zod';
import type {
  anualSchema,
  trimestreSchema,
  mercadoSchema,
  historicoItemSchema,
  referenciaSchema,
} from '@/services/schemas/indicadores.schema';

type Exatamente<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;
type Afirma<T extends true> = T;

export type _AnualBate = Afirma<Exatamente<z.infer<typeof anualSchema>, BlocoAnual>>;
export type _TrimestreBate = Afirma<Exatamente<z.infer<typeof trimestreSchema>, BlocoTrimestral>>;
export type _MercadoBate = Afirma<Exatamente<z.infer<typeof mercadoSchema>, Mercado>>;
export type _HistoricoBate = Afirma<Exatamente<z.infer<typeof historicoItemSchema>, HistoricoItem>>;
export type _ReferenciaBate = Afirma<Exatamente<z.infer<typeof referenciaSchema>, Referencia>>;
