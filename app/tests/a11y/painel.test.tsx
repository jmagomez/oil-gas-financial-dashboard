import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import axe from 'axe-core';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PainelComparativo } from '@/components/features/painel-comparativo';
import payloadReal from '../fixtures/payload.json';

/**
 * O painel e uma TABELA de dados, e tabela e onde cabecalho sem `scope`,
 * celula sem associacao e `caption` ausente passam despercebidos no olho.
 *
 * Limite conhecido: axe nao substitui leitor de tela real. Ele pega rotulo
 * ausente, ordem de heading e ARIA invalido -- a maior parte do que se erra
 * sem perceber.
 */
async function semViolacoes(container: HTMLElement) {
  const r = await axe.run(container, {
    rules: { 'color-contrast': { enabled: false } }, // jsdom nao calcula cor
  });
  expect(r.violations.map((v) => `${v.id}: ${v.description}`).join('\n')).toBe('');
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(payloadReal) } as Response),
    ),
  );
});
afterEach(() => vi.unstubAllGlobals());

describe('acessibilidade do comparativo', () => {
  it('nao tem violacoes de axe', async () => {
    const { container } = render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <PainelComparativo />
      </QueryClientProvider>,
    );
    await screen.findByRole('table', { name: /Receita, EBITDA/ });
    await semViolacoes(container);
  });

  it('a tabela tem caption e cabecalhos com scope', async () => {
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <PainelComparativo />
      </QueryClientProvider>,
    );
    const t = await screen.findByRole('table', { name: /Receita, EBITDA/ });
    expect(t.querySelector('caption')?.textContent?.trim()).toBeTruthy();
    for (const th of t.querySelectorAll('th')) {
      expect(th.getAttribute('scope')).toMatch(/^(col|row)$/);
    }
  });
});
