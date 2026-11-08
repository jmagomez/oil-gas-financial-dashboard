/**
 * Valida o indicadores_oleo_gas.json publicado pelo pipeline contra o schema.
 *
 * Roda no deploy ANTES de publicar: se o pipeline renomeou um campo, a falha
 * acontece aqui e o site no ar continua sendo o ultimo bom. Sem isso o campo
 * ausente vira `undefined` e so aparece como grafico vazio em producao.
 *
 * Uso:  npx tsx scripts/validate-data-contract.ts [caminho]
 *       (padrao: ../indicadores_oleo_gas.json -- a fonte unica, na raiz)
 */
import { readFileSync, existsSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { ZodTypeAny, z } from 'zod';
import { payloadSchema } from '../src/services/schemas/indicadores.schema.js';
import { dadosSchema } from '../src/services/schemas/dashboard-data.schema.js';

const RAIZ = process.argv[2] ?? join(import.meta.dirname, '..', '..');

/**
 * A fonte curada (so primarios) E o gerado (com os 18 derivados).
 *
 * Os dois, de proposito: o app consome o gerado, mas se o pipeline quebrar o
 * contrato da FONTE o gerado sai errado em silencio. Validar so o consumido
 * deixaria passar o erro na origem.
 */
function valida<S extends ZodTypeAny>(arquivo: string, schema: S): z.infer<S> {
  const caminho = resolve(join(RAIZ, arquivo));
  if (!existsSync(caminho)) {
    console.error(`FALTA   ${caminho}`);
    process.exit(1);
  }
  const r = schema.safeParse(JSON.parse(readFileSync(caminho, 'utf8')));
  if (!r.success) {
    console.error(`INVALIDO ${arquivo}`);
    for (const issue of r.error.issues.slice(0, 20)) {
      console.error(`   ${issue.path.join('.') || '(raiz)'}: ${issue.message}`);
    }
    if (r.error.issues.length > 20) {
      console.error(`   ... e mais ${r.error.issues.length - 20} problema(s)`);
    }
    process.exit(1);
  }
  console.log(`OK      ${arquivo}`);
  return r.data as z.infer<S>;
}

valida('indicadores_oleo_gas.json', payloadSchema);
const gerado = valida('dashboard_data.json', dadosSchema);
const { referencia, empresas } = gerado;
console.log(`OK      ${empresas.length} empresas, dados v${referencia.versao_dados}`);
console.log(`        atualizado em ${referencia.atualizado_em}`);

// Avisos: nao reprovam o deploy, mas ficam no log porque sao coisas que a tela
// precisa tratar e que mudam em silencio se ninguem olhar.
const trimestres = new Set(empresas.map((e) => e.q_recente.trimestre));
if (trimestres.size > 1) {
  console.warn(
    `aviso   as empresas estao em trimestres DIFERENTES (${[...trimestres].sort().join(', ')})` +
      ` -- nenhuma coluna pode ser rotulada com um trimestre unico`,
  );
}
for (const e of empresas) {
  if (e.fy2025.producao_kboed === null) {
    console.warn(
      `aviso   ${e.ticker}: producao ausente em FY2025 -- indicadores por boe ficam ausentes`,
    );
  }
  if (e.fy2025.roe_pct !== null && Math.abs(e.fy2025.roe_pct) < 1) {
    console.warn(
      `aviso   ${e.ticker}: ROE de ${e.fy2025.roe_pct}% em FY2025 -- patrimonio nao e estimavel, gearing fica indisponivel`,
    );
  }
}
const janelas = new Set(empresas.map((e) => e.historico.length));
if (janelas.size > 1) {
  console.warn(
    `aviso   historico com janelas irregulares (${[...janelas].sort().join(', ')} trimestres)` +
      ` -- comparar posicao na faixa entre empresas exige mostrar o n`,
  );
}
console.log('\nContrato de dados conferido.');
