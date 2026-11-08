import { buscaJson, ErroDeDados } from './http-client';
import { dadosSchema } from './schemas/dashboard-data.schema';
import type { Dados } from '@/types/dashboard-data';

const ARQUIVO = 'dashboard_data.json';

/**
 * Le o payload enriquecido e valida antes de devolver. Dado fora do contrato
 * falha aqui nomeando o campo e a empresa, em vez de virar `undefined` num
 * grafico vazio tres camadas adiante.
 */
export async function carregaDados(): Promise<Dados> {
  const bruto = await buscaJson(ARQUIVO);
  const r = dadosSchema.safeParse(bruto);
  if (!r.success) {
    const primeiro = r.error.issues[0];
    const onde = primeiro ? `${primeiro.path.join('.') || '(raiz)'}: ${primeiro.message}` : '';
    throw new ErroDeDados(`${ARQUIVO} fora do contrato — ${onde}`, ARQUIVO, r.error);
  }
  return r.data;
}
