import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from '@/app/App';
import { Providers } from '@/app/providers';
import '@/styles/globals.css';

const raiz = document.getElementById('root');
if (!raiz) throw new Error('elemento #root não encontrado em index.html');

createRoot(raiz).render(
  <StrictMode>
    <Providers>
      <App />
    </Providers>
  </StrictMode>,
);
