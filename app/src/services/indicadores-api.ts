import { buscaJson, ErroDeDados } from './http-client';
import { payloadSchema } from './schemas/indicadores.schema';
import type { Payload } from '@/types/indicadores';

const ARQUIVO = 'indicadores_oleo_gas.json';

/**
 * Unico ponto que le o payload, e ele valida ANTES de devolver: dado fora do
 * contrato falha aqui, nomeando o campo e a empresa, em vez de virar
 * `undefined` num grafico vazio tres camadas adiante.
 */
export async function carregaIndicadores(): Promise<Payload> {
  const bruto = await buscaJson(ARQUIVO);
  const r = payloadSchema.safeParse(bruto);
  if (!r.success) {
    const primeiro = r.error.issues[0];
    const onde = primeiro ? `${primeiro.path.join('.') || '(raiz)'}: ${primeiro.message}` : '';
    throw new ErroDeDados(`${ARQUIVO} fora do contrato — ${onde}`, ARQUIVO, r.error);
  }
  return r.data;
}
