import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PainelComparativo } from '@/components/features/painel-comparativo';
import payloadReal from '../fixtures/dashboard-data.json';

/**
 * Fixture recortada do payload ENRIQUECIDO: XOM (normal), BP (ROE ~0), SHEL,
 * EQNR (caixa liquido). E o dashboard_data.json, e nao o curado, porque a
 * coluna EV / EBITDA le `derivados.ev_ebitda_x` -- derivado no
 * build_dashboard.py, que e o unico lugar do projeto que calcula indicador.
 */
function envolve(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
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

const tabela = () => screen.findByRole('table', { name: /Receita, EBITDA/ });
const linha = async (ticker: string) =>
  within(await tabela()).getByRole('row', { name: new RegExp(`^${ticker}\\b`) });

describe('PainelComparativo', () => {
  it('monta uma linha por empresa, com o pais ao lado do ticker', async () => {
    render(envolve(<PainelComparativo />));
    const t = await tabela();
    for (const tk of ['XOM', 'BP', 'EQNR']) {
      expect(within(t).getByRole('rowheader', { name: new RegExp(`^${tk}`) })).toBeInTheDocument();
    }
  });

  it('formata os valores em pt-BR', async () => {
    render(envolve(<PainelComparativo />));
    expect(within(await linha('XOM')).getByText('323.910')).toBeInTheDocument();
  });

  it('a Equinor aparece como CAIXA LIQUIDO, nao como alavancagem negativa', async () => {
    render(envolve(<PainelComparativo />));
    const l = await linha('EQNR');
    expect(within(l).getByText(/caixa líquido/)).toBeInTheDocument();
    // Nada de "-40%" nessa celula: seria comparavel a um gearing positivo.
    expect(within(l).queryByText(/-\d+,\d%/)).toBeNull();
  });

  it('a BP mostra alavancagem indisponivel COM o motivo, nao um numero fragil', async () => {
    render(envolve(<PainelComparativo />));
    const l = await linha('BP');
    expect(within(l).getByText(/ROE de 0\.1% é baixo demais/)).toBeInTheDocument();
  });

  it('a XOM tem gearing calculado', async () => {
    render(envolve(<PainelComparativo />));
    expect(within(await linha('XOM')).getByText('10,9%')).toBeInTheDocument();
  });

  it('mostra o trimestre DE CADA empresa, nao um rotulo global', async () => {
    render(envolve(<PainelComparativo />));
    const t = await tabela();
    // No payload real XOM esta em Q2 2026 e BP em Q3 2026.
    expect(within(await linha('XOM')).getByText('2T26')).toBeInTheDocument();
    expect(within(await linha('BP')).getByText('3T26')).toBeInTheDocument();
    // E o cabecalho NAO afirma um trimestre unico.
    expect(within(t).queryByRole('columnheader', { name: /Q[23] 2026/ })).toBeNull();
  });

  it('a posicao na faixa vem acompanhada do n, porque as janelas diferem', async () => {
    render(envolve(<PainelComparativo />));
    const t = await tabela();
    expect(within(t).getAllByText(/\(n=\d\)/).length).toBeGreaterThan(0);
  });

  it('explica em texto visivel por que a estimativa de patrimonio pode falhar', async () => {
    render(envolve(<PainelComparativo />));
    await tabela();
    // A nota tem de dizer as DUAS coisas: que o patrimonio sai do ROE e por
    // que nao sai do D/E. Sem a segunda, a escolha parece arbitraria.
    expect(screen.getByText(/itens não recorrentes/)).toBeInTheDocument();
    expect(screen.getByText(/estimado por lucro ÷ ROE/)).toBeInTheDocument();
    expect(screen.getByText(/e não líquida/)).toBeInTheDocument();
  });

  it('avisa que as empresas estao em trimestres diferentes', async () => {
    render(envolve(<PainelComparativo />));
    await tabela();
    expect(screen.getByText(/divulgam em datas distintas/)).toBeInTheDocument();
  });
});
