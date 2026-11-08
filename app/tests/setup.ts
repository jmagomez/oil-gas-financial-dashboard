import '@testing-library/jest-dom/vitest';

// Recharts mede o container com ResizeObserver, que o jsdom nao tem.
if (!('ResizeObserver' in globalThis)) {
  (globalThis as { ResizeObserver?: unknown }).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// use-theme le a preferencia do sistema.
//
// O guard de `typeof window` nao e defensividade vazia: o teste do dev server
// roda em ambiente `node` (faz HTTP de verdade, nao renderiza nada) e este
// setup e aplicado a TODA a suite. Sem o guard, ele estoura com
// "window is not defined" antes de qualquer teste daquele arquivo rodar.
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = (q: string) => ({
    matches: false,
    media: q,
    onchange: null,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
    dispatchEvent: () => false,
  });
}
