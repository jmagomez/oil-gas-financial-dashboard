import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Nomes que o dev server aceita servir da RAIZ do repositorio.
 *
 * Lista de permissao, nao sanitizacao: qualquer esquema que monte o caminho a
 * partir da URL precisa depois se defender de `..`, e defesa que depende de
 * acertar a sanitizacao e defesa que uma hora falha. Com a lista, um nome fora
 * dela simplesmente nao e servido.
 */
const DADOS_DA_RAIZ = new Set(['indicadores_oleo_gas.json', 'dashboard_data.json']);

/**
 * Serve os JSON da raiz do repositorio em /data/ durante o `npm run dev`.
 *
 * Por que um middleware e nao `server.proxy`: proxy encaminha para OUTRO
 * servidor, e aqui nao ha outro -- o arquivo esta no disco, um nivel acima da
 * raiz do Vite. A primeira versao usava proxy com `bypass`, e o resultado era
 * que /data/indicadores_oleo_gas.json devolvia o index.html (o fallback do
 * SPA, 1.402 bytes) e /data/dashboard_data.json devolvia HTTP 500. Em dev o
 * app recebia HTML e quebrava no response.json(). Nao havia teste cobrindo o
 * dev server, e o defeito passou da primeira publicacao.
 */
function serveDadosDaRaiz(): Plugin {
  return {
    name: 'serve-dados-da-raiz',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/data', (req, res, next) => {
        const nome = (req.url ?? '').replace(/^\//, '').split('?')[0] ?? '';
        if (!DADOS_DA_RAIZ.has(nome)) return next();
        const caminho = fileURLToPath(new URL(`../${nome}`, import.meta.url));
        if (!existsSync(caminho)) return next();
        res.setHeader('Content-Type', 'application/json; charset=utf-8');
        // Sem cache: em dev o arquivo muda quando o pipeline roda.
        res.setHeader('Cache-Control', 'no-store');
        res.end(readFileSync(caminho));
      });
    },
  };
}

export default defineConfig(({ command }) => ({
  plugins: [react(), serveDadosDaRaiz()],

  // Publicado em /oil-gas-financial-dashboard/app/ -- o repositorio serve o
  // dashboard do pipeline na raiz e este app no subcaminho, enquanto as
  // analises migram uma a uma.
  base: command === 'build' ? '/oil-gas-financial-dashboard/app/' : '/',

  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },

  server: {
    // Em dev os JSON vem da RAIZ do repositorio, pelo middleware acima. Nao ha
    // copia dentro de app/: fonte unica de verdade continua sendo um arquivo.
    // No deploy, o workflow copia os mesmos arquivos para /app/data/.
    fs: { allow: ['..'] },
  },

  build: {
    sourcemap: true,
    rollupOptions: {
      output: {
        // Recharts pesa mais que o payload inteiro. Separar o vendor de React
        // do resto mantem o chunk de entrada pequeno; os paineis entram por
        // lazy() e ganham chunk proprio automaticamente.
        manualChunks: { react: ['react', 'react-dom'] },
      },
    },
  },

  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    globals: true,
  },
}));
