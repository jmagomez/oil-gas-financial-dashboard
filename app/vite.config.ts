import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig(({ command }) => ({
  plugins: [react()],

  // Publicado em /oil-gas-financial-dashboard/app/ -- o repositorio serve o
  // dashboard do pipeline na raiz e este app no subcaminho, enquanto as
  // analises migram uma a uma.
  base: command === 'build' ? '/oil-gas-financial-dashboard/app/' : '/',

  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },

  server: {
    // Em dev o dado vem do JSON da RAIZ do repositorio, por proxy. Nao ha
    // copia dentro de app/: fonte unica de verdade continua sendo um arquivo.
    // No deploy, o workflow copia o mesmo arquivo para /app/data/.
    proxy: {
      '/data': {
        target: 'http://localhost:5173',
        bypass: (req) =>
          req.url === '/data/indicadores_oleo_gas.json'
            ? '/../indicadores_oleo_gas.json'
            : undefined,
      },
    },
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
