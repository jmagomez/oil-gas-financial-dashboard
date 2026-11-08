import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from 'axe-core';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PainelPonte } from '@/components/features/painel-ponte';
import { PainelEficiencia } from '@/components/features/painel-eficiencia';
import { PainelValuation } from '@/components/features/painel-valuation';
import { PainelPerfil } from '@/components/features/painel-perfil';
import dadosReais from '../fixtures/dashboard-data.json';

/**
 * Os quatro paineis de grafico. O ponto desta suite e o motivo da reescrita:
 * o dashboard antigo desenha em 65 <canvas>, que sao opacos para leitor de
 * tela. Aqui cada grafico e SVG com rotulo acessivel E tabela equivalente --
 * e estes testes impedem que isso regrida.
 */
function env() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}

async function semViolacoes(container: HTMLElement) {
  const r = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
  expect(r.violations.map((v) => `${v.id}: ${v.description}`).join('\n')).toBe('');
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(dadosReais) } as Response)),
  );
});
afterEach(() => vi.unstubAllGlobals());

const PAINEIS = [
  ['ponte de caixa', <PainelPonte key="p" />, /Da receita ao caixa livre/],
  ['eficiência', <PainelEficiencia key="e" />, /EBITDA por barril equivalente/],
  ['valuation', <PainelValuation key="v" />, /Múltiplo contra retorno/],
  ['perfil', <PainelPerfil key="r" />, /Radar de perfil/],
] as const;

describe('acessibilidade dos paineis de grafico', () => {
  for (const [nome, painel, ancora] of PAINEIS) {
    it(`${nome} nao tem violacoes de axe`, async () => {
      const { container } = render(
        <QueryClientProvider client={env()}>{painel}</QueryClientProvider>,
      );
      await screen.findByText(ancora);
      await semViolacoes(container);
    });

    it(`${nome}: todo grafico tem rotulo acessivel`, async () => {
      render(<QueryClientProvider client={env()}>{painel}</QueryClientProvider>);
      await screen.findByText(ancora);
      const graficos = screen.getAllByRole('img');
      expect(graficos.length).toBeGreaterThan(0);
      for (const g of graficos) {
        // Rotulo com conteudo de verdade, nao so o titulo repetido: e o que
        // um leitor de tela anuncia no lugar do SVG.
        expect((g.getAttribute('aria-label') ?? '').length).toBeGreaterThan(40);
      }
    });

    it(`${nome}: a tabela equivalente abre e tem cabecalho de linha`, async () => {
      render(<QueryClientProvider client={env()}>{painel}</QueryClientProvider>);
      await screen.findByText(ancora);
      const botoes = screen.getAllByRole('button', { name: /dados em tabela/ });
      expect(botoes.length).toBeGreaterThan(0);
      await userEvent.click(botoes[0]!);
      const t = screen.getAllByRole('table')[0]!;
      expect(t.querySelector('caption')?.textContent?.trim()).toBeTruthy();
      expect(t.querySelectorAll('th[scope="row"]').length).toBeGreaterThan(0);
      expect(t.querySelectorAll('th[scope="col"]').length).toBeGreaterThan(0);
    });
  }
});
