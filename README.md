# Dashboard Financeiro — Óleo & Gás

Dashboard comparativo com 18 indicadores financeiros e operacionais de 7 grandes petroleiras: **ExxonMobil, Chevron, Shell, BP, Equinor, TotalEnergies e Petrobras**.

Períodos cobertos: ano fiscal **FY2025** (encerrado em 31/12/2025) e o trimestre mais recente divulgado, **Q1 2026** (encerrado em 31/03/2026). Dados consultados em 20/07/2026, revisados em 21/07/2026.

**Dashboard ao vivo (GitHub Pages):** https://jmagomez.github.io/oil-gas-financial-dashboard/dashboard_oleo_gas.html

## Arquivos

- `dashboard_oleo_gas.html` — dashboard interativo, **gerado automaticamente** (não editar à mão). Filtra por empresa, ordena a tabela clicando nas colunas, alterna FY2025/trimestre, e traz gráficos comparativos de receita, lucro líquido, EBITDA, FCF, dívida líquida, ROE/ROA, produção, market cap, múltiplos (P/E, EV/EBITDA) e dividend yield.
- `dashboard_template.html` — esqueleto estático do dashboard (HTML/CSS/JS), com o placeholder `__DATA_JSON__` onde os dados são injetados.
- `indicadores_oleo_gas.json` — **fonte única de verdade** dos dados: indicadores por empresa/período, notas metodológicas e fontes.
- `indicadores_oleo_gas.csv` — mesma base em formato tabular (uma linha por empresa/período), gerada automaticamente a partir do JSON.
- `build_dashboard.py` — script que gera `dashboard_oleo_gas.html` e `indicadores_oleo_gas.csv` a partir do template + JSON, com checagens básicas de sanidade dos dados (ex.: lucro maior que receita, EBITDA fora de escala, fontes ausentes).

## Como atualizar os dados

1. Edite `indicadores_oleo_gas.json` (único arquivo de dados a editar manualmente).
2. Rode `python3 build_dashboard.py`.
3. Confira os avisos de validação impressos no terminal (se houver).
4. Suba os arquivos alterados (`indicadores_oleo_gas.json`, `.csv` e `dashboard_oleo_gas.html`) para o repositório.

Isso substitui o processo manual anterior (editar o HTML final diretamente e injetar o JSON via `sed`/scripts ad-hoc a cada atualização), reduzindo o risco de inconsistência entre o dashboard e a planilha.

## Indicadores incluídos

Receita total, lucro líquido, EBITDA, margem líquida, fluxo de caixa operacional, free cash flow, capex, dívida líquida, dívida/patrimônio, ROE, ROA, produção (mil boe/d), market cap, P/E, EV/EBITDA, dividend yield e preço da ação.

## Metodologia e fontes

- Fonte principal: [stockanalysis.com](https://stockanalysis.com) (financials, balance-sheet, cash-flow-statement, statistics, metrics), complementada por press releases oficiais (Shell, BP, Equinor, TotalEnergies) para dívida líquida/gearing e produção.
- **Petrobras**: demonstrações originais em BRL, convertidas para USD com taxa média implícita (~R$5,58/US$ em FY2025; ~R$5,25/US$ em Q1 2026). Métricas de mercado já nativas em USD (ADR na NYSE).
- **BP/Shell**: dívida líquida e gearing na metodologia oficial (não-IFRS) de cada empresa.
- **BP FY2025**: lucro líquido atribuível aos acionistas próximo de zero (US$ 55 milhões) por itens não recorrentes.
- Equinor e TotalEnergies têm caixa líquido positivo (dívida líquida negativa) em ambos os períodos.
- **Dividend yield da Petrobras**: confirmado em ~5,34% (stockanalysis.com), mas varia bastante entre fontes (5,3% a 9,3%) por diferenças de metodologia e pela política de dividendos variável da empresa — tratar como faixa, não número único.
- Ver notas completas e URLs de fonte por empresa dentro do `indicadores_oleo_gas.json` e no rodapé do dashboard.

⚠️ Dados de mercado (cotação, market cap, P/E, yield) são spot em 20/07/2026 — ficarão desatualizados com o tempo.

## Issue relacionada

O conector GitHub MCP usado para automatizar parte deste workflow não suporta `create_repository` via API (falta a permissão "Administration" no manifesto do app) — acompanhar em [anthropics/claude-ai-mcp#655](https://github.com/anthropics/claude-ai-mcp/issues/655).
