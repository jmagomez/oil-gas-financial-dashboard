# Dashboard Financeiro — Óleo & Gás

Dashboard comparativo com 17 indicadores financeiros e operacionais de 7 grandes petroleiras: **ExxonMobil, Chevron, Shell, BP, Equinor, TotalEnergies e Petrobras**.

Períodos cobertos: ano fiscal **FY2025** (encerrado em 31/12/2025) e o trimestre mais recente divulgado, **Q1 2026** (encerrado em 31/03/2026). Dados consultados em 20/07/2026.

## Arquivos

- `dashboard_oleo_gas.html` — dashboard interativo (abra直接 no navegador). Permite filtrar por empresa, alternar entre FY2025/trimestre na tabela, e traz gráficos comparativos de receita, lucro líquido, EBITDA, FCF, dívida líquida, ROE/ROA, produção, market cap, múltiplos (P/E, EV/EBITDA) e dividend yield.
- `indicadores_oleo_gas.json` — dados estruturados (fonte única usada pelo dashboard), incluindo notas metodológicas e fontes por empresa.
- `indicadores_oleo_gas.csv` — mesma base em formato tabular, uma linha por empresa/período, pronta para Excel/Google Sheets/Python.

## Indicadores incluídos

Receita total, lucro líquido, EBITDA, margem líquida, fluxo de caixa operacional, free cash flow, capex, dívida líquida, dívida/patrimônio, ROE, ROA, produção (mil boe/d), market cap, P/E, EV/EBITDA, dividend yield e preço da ação.

## Metodologia e fontes

- Fonte principal: [stockanalysis.com](https://stockanalysis.com) (financials, balance-sheet, cash-flow-statement, statistics, metrics), complementada por press releases oficiais (Shell, BP, Equinor, TotalEnergies) para dívida líquida/gearing e produção.
- **Petrobras**: demonstrações originais em BRL, convertidas para USD com taxa média implícita (~R$5,58/US$ em FY2025; ~R$5,25/US$ em Q1 2026). Métricas de mercado já nativas em USD (ADR na NYSE).
- **BP/Shell**: dívida líquida e gearing na metodologia oficial (não-IFRS) de cada empresa.
- **BP FY2025**: lucro líquido atribuível aos acionistas próximo de zero (US$ 55 milhões) por itens não recorrentes.
- Equinor e TotalEnergies têm caixa líquido positivo (dívida líquida negativa) em ambos os períodos.
- Ver notas completas e URLs de fonte por empresa dentro do `indicadores_oleo_gas.json` e no rodapé do dashboard HTML.

⚠️ Dados de mercado (cotação, market cap, P/E, yield) são spot em 20/07/2026 — ficarão desatualizados com o tempo. O dividend yield da Petrobras carece de confirmação adicional (ver nota no JSON).
