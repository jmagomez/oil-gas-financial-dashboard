// @vitest-environment node
import { readFileSync } from 'node:fs';
import { fileURLToPath, URL } from 'node:url';
import { createServer, type ViteDevServer } from 'vite';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

/**
 * O unico teste da suite que sobe um servidor de verdade e faz HTTP.
 *
 * Existe por causa de um defeito que sobreviveu a primeira publicacao: o
 * `npm run dev` nao servia os dados. A versao anterior do vite.config usava
 * `server.proxy` com `bypass`, e proxy encaminha para OUTRO servidor -- aqui
 * nao ha outro, o arquivo esta no disco um nivel acima da raiz do Vite. O
 * resultado era `/data/indicadores_oleo_gas.json` devolvendo o index.html
 * (1.402 bytes, HTTP 200) e `/data/dashboard_data.json` devolvendo HTTP 500.
 * Em dev o app recebia HTML e quebrava no `response.json()`.
 *
 * Nada no gate cobria isso. Typecheck, lint, testes de componente e build
 * passam todos com o dev server quebrado, porque nenhum deles o executa.
 *
 * DUAS DECISOES QUE FAZEM O TESTE VALER ALGO:
 *
 * 1. Sobe o servidor a partir do `root` do app, deixando o Vite RESOLVER o
 *    vite.config.ts real. Montar uma configuracao a mao aqui testaria o
 *    teste, nao o projeto -- e nao pegaria a regressao que motivou tudo isto.
 *
 * 2. Afirma que a resposta NAO e HTML, e nao apenas que veio 200. O bug
 *    original devolvia 200: era o fallback do SPA. Checar so o status code
 *    deixaria passar exatamente o defeito que este arquivo persegue.
 *
 * Custo honesto: e o teste mais lento e o unico com ciclo de vida de
 * servidor. Porta efemera (`port: 0`) para nao colidir em CI.
 */

const RAIZ_APP = fileURLToPath(new URL('../..', import.meta.url));
const RAIZ_REPO = fileURLToPath(new URL('../../..', import.meta.url));

/** Os dois nomes que o middleware deve servir, com o tamanho real em disco. */
const SERVIDOS = ['indicadores_oleo_gas.json', 'dashboard_data.json'] as const;

let servidor: ViteDevServer;
let base: string;

beforeAll(async () => {
  servidor = await createServer({
    root: RAIZ_APP,
    // `configFile` default: o Vite acha o vite.config.ts do root. E o ponto.
    logLevel: 'silent',
    server: { port: 0, strictPort: false },
  });
  await servidor.listen();
  const url = servidor.resolvedUrls?.local[0];
  if (!url) throw new Error('o dev server subiu sem URL local');
  base = url.replace(/\/$/, '');
}, 90_000);

afterAll(async () => {
  await servidor?.close();
});

describe('dev server: os JSON da raiz em /data/', () => {
  for (const nome of SERVIDOS) {
    it(`serve ${nome} como JSON, identico ao arquivo em disco`, async () => {
      const r = await fetch(`${base}/data/${nome}`);
      const corpo = await r.text();

      expect(r.status).toBe(200);
      expect(r.headers.get('content-type')).toMatch(/application\/json/);

      // A assercao que pega o bug original: ele devolvia 200 com index.html.
      expect(corpo.trimStart().startsWith('<!doctype')).toBe(false);
      expect(corpo).not.toMatch(/<html/i);

      // E o conteudo e o arquivo de verdade, nao um stub do mesmo tipo.
      const emDisco = readFileSync(`${RAIZ_REPO}/${nome}`, 'utf8');
      expect(corpo).toBe(emDisco);
      // Corpo de BLOCO, nao expressao: `() => JSON.parse(x)` devolveria `any`
      // e o lint reprova com razao. O que interessa aqui e nao lancar.
      expect(() => {
        JSON.parse(corpo);
      }).not.toThrow();
    }, 30_000);
  }

  it('o payload enriquecido chega com os derivados e os eixos do radar', async () => {
    // Nao basta ser JSON valido: o app depende destes campos, e servir o
    // arquivo primario no lugar do enriquecido passaria nas checagens acima.
    const r = await fetch(`${base}/data/dashboard_data.json`);
    const d = (await r.json()) as {
      empresas: { fy2025: { derivados?: unknown }; perfil?: unknown }[];
      meta_build?: { eixos_perfil?: unknown };
    };
    expect(d.empresas.length).toBeGreaterThan(0);
    expect(d.empresas[0]?.fy2025.derivados).toBeDefined();
    expect(d.empresas[0]?.perfil).toBeDefined();
    expect(d.meta_build?.eixos_perfil).toBeDefined();
  }, 30_000);

  it('nome fora da lista de permissao NAO e servido como JSON', async () => {
    // A defesa e lista de permissao, nao sanitizacao: o que nao esta na lista
    // cai no fallback do SPA.
    const r = await fetch(`${base}/data/qualquer-coisa.json`);
    expect(r.headers.get('content-type')).not.toMatch(/application\/json/);
  }, 30_000);

  it('tentativa de travessia de caminho NAO devolve arquivo do sistema', async () => {
    const r = await fetch(`${base}/data/..%2f..%2fetc%2fpasswd`);
    const corpo = await r.text();
    expect(corpo).not.toMatch(/root:/);
    expect(r.headers.get('content-type')).not.toMatch(/application\/json/);
  }, 30_000);
});
