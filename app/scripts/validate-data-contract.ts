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
import { payloadSchema } from '../src/services/schemas/indicadores.schema.js';

const CAMINHO = resolve(
  process.argv[2] ?? join(import.meta.dirname, '..', '..', 'indicadores_oleo_gas.json'),
);

if (!existsSync(CAMINHO)) {
  console.error(`FALTA   ${CAMINHO}`);
  process.exit(1);
}

const r = payloadSchema.safeParse(JSON.parse(readFileSync(CAMINHO, 'utf8')));

if (!r.success) {
  console.error(`INVALIDO ${CAMINHO}`);
  for (const issue of r.error.issues.slice(0, 20)) {
    console.error(`   ${issue.path.join('.') || '(raiz)'}: ${issue.message}`);
  }
  if (r.error.issues.length > 20) {
    console.error(`   ... e mais ${r.error.issues.length - 20} problema(s)`);
  }
  process.exit(1);
}

const { referencia, empresas } = r.data;
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
