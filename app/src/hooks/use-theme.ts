import { useCallback, useEffect, useState } from 'react';

type Tema = 'claro' | 'escuro';

function temaInicial(): Tema {
  // Le a classe que o script bloqueante do index.html ja aplicou, em vez de
  // recalcular: recalcular aqui pode discordar do que esta na tela.
  return document.documentElement.classList.contains('dark') ? 'escuro' : 'claro';
}

export function useTheme() {
  const [tema, setTema] = useState<Tema>(temaInicial);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', tema === 'escuro');
    try {
      localStorage.setItem('tema', tema);
    } catch {
      // Modo privado ou storage bloqueado: o tema vale para esta sessao.
    }
  }, [tema]);

  // Segue a preferencia do sistema ENQUANTO o usuario nao escolheu: quem
  // escolheu explicitamente nao quer que o sistema mude por ele.
  useEffect(() => {
    let escolheu = false;
    try {
      escolheu = localStorage.getItem('tema') !== null;
    } catch {
      escolheu = false;
    }
    if (escolheu) return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const ouvinte = (e: MediaQueryListEvent) => setTema(e.matches ? 'escuro' : 'claro');
    mq.addEventListener('change', ouvinte);
    return () => mq.removeEventListener('change', ouvinte);
  }, []);

  const alterna = useCallback(() => {
    setTema((t) => (t === 'escuro' ? 'claro' : 'escuro'));
  }, []);

  return { tema, alterna };
}
