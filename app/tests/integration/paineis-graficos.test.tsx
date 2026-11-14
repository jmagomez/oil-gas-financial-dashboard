import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PainelPonte } from '@/components/features/painel-ponte';
import { PainelEficiencia } from '@/components/features/painel-eficiencia';
import { PainelValuation } from '@/components/features/painel-valuation';
import { PainelPerfil } from '@/components/features/painel-perfil';
import dadosReais from '../fixtures/dashboard-data.json';

/** Fixture do payload enriquecido real: XOM, SHEL (resíduo) e EQNR (proxy). */
function envolve(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(dadosReais) } as Response)),
  );
});
afterEach(() => vi.unstubAllGlobals());

describe('PainelPonte', () => {
  it('monta a ponte da primeira empresa e lista os passos na tabela', async () => {
    render(envolve(<PainelPonte />));
    await screen.findByText('Da receita ao caixa livre');
    await userEvent.click(screen.getByRole('button', { name: /dados em tabela/ }));
    const t = screen.getByRole('table');
    for (const passo of ['Receita', 'EBITDA', 'Capex', 'Free cash flow']) {
      expect(within(t).getByRole('rowheader', { name: passo })).toBeInTheDocument();
    }
  });

  it('agrega capital de giro, impostos e juros num passo, e DIZ que agrega', async () => {
    render(envolve(<PainelPonte />));
    await screen.findByText('Da receita ao caixa livre');
    expect(screen.getByText(/a fonte não os abre em campos separados/)).toBeInTheDocument();
  });

  it('expoe o residuo da Shell em vez de forcar as barras a fechar', async () => {
    render(envolve(<PainelPonte />));
    await screen.findByText('Da receita ao caixa livre');
    await userEvent.selectOptions(screen.getByLabelText('Empresa'), 'SHEL');
    expect(await screen.findByText(/Resíduo de US\$ 1 mi \(arredondamento\)/)).toBeInTheDocument();
    expect(screen.getByText(/ajustá-las esconderia a diferença/)).toBeInTheDocument();
  });

  it('o grafico tem rotulo acessivel com os valores, nao um SVG mudo', async () => {
    render(envolve(<PainelPonte />));
    const img = await screen.findByRole('img', { name: /Ponte de caixa de ExxonMobil/ });
    expect(img).toHaveAccessibleName(/Receita 323\.910/);
  });
});

describe('PainelEficiencia', () => {
  it('avisa quando a producao do periodo veio por procuracao', async () => {
    render(envolve(<PainelEficiencia />));
    // EQNR usa proxy em FY2025, que e o periodo inicial.
    expect(await screen.findByText(/Produção por procuração em EQNR/)).toBeInTheDocument();
  });

  it('diz que receita por boe NAO e realizacao de upstream', async () => {
    render(envolve(<PainelEficiencia />));
    await screen.findByText('Receita por barril equivalente');
    expect(screen.getByText(/Não é realização de upstream/)).toBeInTheDocument();
  });

  it('ao trocar para o trimestre, avisa que as empresas estao em trimestres diferentes', async () => {
    render(envolve(<PainelEficiencia />));
    await screen.findByText('Eficiência operacional');
    await userEvent.click(screen.getByRole('radio', { name: 'trimestre' }));
    expect(await screen.findByText(/não existe um único/)).toBeInTheDocument();
  });

  it('avisa quando a producao do denominador e de outro trimestre', async () => {
    render(envolve(<PainelEficiencia />));
    await screen.findByText('Eficiência operacional');
    await userEvent.click(screen.getByRole('radio', { name: 'trimestre' }));
    // BP, SHEL e EQNR estao em Q3 2026 nos fundamentos com producao do Q2 2026.
    const aviso = await screen.findByText(/Produção de outro trimestre em/);
    expect(aviso).toHaveTextContent('BP (Q2 2026)');
    expect(aviso).toHaveTextContent('SHEL (Q2 2026)');
  });

  it('nao acusa defasagem na XOM, cuja producao e do trimestre exibido', async () => {
    render(envolve(<PainelEficiencia />));
    await screen.findByText('Eficiência operacional');
    await userEvent.click(screen.getByRole('radio', { name: 'trimestre' }));
    const aviso = await screen.findByText(/Produção de outro trimestre em/);
    expect(aviso).not.toHaveTextContent('XOM');
  });

  it('o aviso de trimestres distintos LE os rotulos do payload, nao os escreve', async () => {
    // Estavam fixos no codigo ("Q2 2026 e Q3 2026"). Um rotulo escrito a mao
    // envelhece sozinho: no dia em que as sete convergirem, o aviso continuaria
    // afirmando uma divergencia que deixou de existir.
    render(envolve(<PainelEficiencia />));
    await screen.findByText('Eficiência operacional');
    await userEvent.click(screen.getByRole('radio', { name: 'trimestre' }));
    const aviso = await screen.findByText(/não existe um único/);
    expect(aviso).toHaveTextContent('Q2 2026');
    expect(aviso).toHaveTextContent('Q3 2026');
    expect(aviso).toHaveTextContent('2 trimestres ao mesmo tempo');
  });

  it('registra que a Shell publica duas bases de producao', async () => {
    render(envolve(<PainelEficiencia />));
    await screen.findByText('Produção');
    expect(screen.getByText(/divergem em cerca de 1,5%/)).toBeInTheDocument();
  });
});

describe('PainelValuation', () => {
  it('carrega os dois graficos de dispersao', async () => {
    render(envolve(<PainelValuation />));
    expect(await screen.findByText('Múltiplo contra retorno')).toBeInTheDocument();
    expect(screen.getByText('Dividend yield contra FCF yield')).toBeInTheDocument();
  });

  it('carrega a ressalva de que o yield da Petrobras e uma faixa', async () => {
    render(envolve(<PainelValuation />));
    await screen.findByText('Dividend yield contra FCF yield');
    expect(screen.getByText(/é uma faixa, não um número/)).toBeInTheDocument();
  });

  it('diz que multiplo de mercado e snapshot, nao fechamento do ano fiscal', async () => {
    render(envolve(<PainelValuation />));
    expect(await screen.findByText(/não são do fechamento do ano fiscal/)).toBeInTheDocument();
  });
});

describe('PainelPerfil', () => {
  it('abre com no maximo tres empresas e permite alternar', async () => {
    render(envolve(<PainelPerfil />));
    await screen.findByText('Radar de perfil');
    const grupo = screen.getByRole('group', { name: 'Empresas no radar' });
    const ativos = within(grupo)
      .getAllByRole('button')
      .filter((b) => b.getAttribute('aria-pressed') === 'true');
    expect(ativos).toHaveLength(3);
  });

  it('nunca deixa o radar sem nenhuma serie', async () => {
    render(envolve(<PainelPerfil />));
    await screen.findByText('Radar de perfil');
    const grupo = screen.getByRole('group', { name: 'Empresas no radar' });
    for (const tk of ['XOM', 'SHEL', 'EQNR']) {
      await userEvent.click(within(grupo).getByRole('button', { name: tk }));
    }
    const ativos = within(grupo)
      .getAllByRole('button')
      .filter((b) => b.getAttribute('aria-pressed') === 'true');
    expect(ativos.length).toBeGreaterThanOrEqual(1);
  });

  it('carrega as DUAS ressalvas do radar: escala relativa e o eixo Valuation', async () => {
    render(envolve(<PainelPerfil />));
    await screen.findByText('Radar de perfil');
    expect(screen.getByText(/Posição relativa, não magnitude/)).toBeInTheDocument();
    expect(screen.getByText(/Ele pontua múltiplo baixo como alto/)).toBeInTheDocument();
  });
});
