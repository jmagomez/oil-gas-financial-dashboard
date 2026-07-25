# Dashboard Financeiro — Óleo & Gás

Dashboard comparativo de **28 indicadores** financeiros, operacionais e de valuation — 17 primários e 11 derivados — de 7 grandes petroleiras: **ExxonMobil, Chevron, Shell, BP, Equinor, TotalEnergies e Petrobras**.

Períodos cobertos: ano fiscal **FY2025** (encerrado em 31/12/2025) e o trimestre mais recente divulgado, **Q1 2026** (encerrado em 31/03/2026). Dados consultados em 20/07/2026.

**Dashboard ao vivo (GitHub Pages):** https://jmagomez.github.io/oil-gas-financial-dashboard/

Os dados de mercado (cotação, market cap, P/E, dividend yield e EV/EBITDA) são atualizados **automaticamente todo dia útil**, após o fechamento de Nova York.

## Arquivos

- `dashboard_oleo_gas.html` — dashboard interativo, **gerado automaticamente** (não editar à mão).
- `index.html` — página de entrada do GitHub Pages; só encaminha para o dashboard.
- `dashboard_template.html` — esqueleto do dashboard (HTML/CSS/JS), com o placeholder `__DATA_JSON__`.
- `indicadores_oleo_gas.json` — **fonte única de verdade**: apenas dados primários, notas metodológicas e fontes. Nenhum indicador derivado é gravado aqui.
- `indicadores_oleo_gas.csv` — mesma base em formato tabular (uma linha por empresa/período), agora com as colunas derivadas.
- `build_dashboard.py` — calcula os derivados, valida os números e gera o HTML e o CSV.
- `update_market_data.py` — rotina que atualiza só os dados de mercado (ver abaixo).
- `requirements-market.txt` — dependência da rotina de mercado (`yfinance`).
- `tests/` — testes de compilação, da camada de derivados e da rotina de mercado (`pytest`).

## Como atualizar os dados

Os dados têm dois regimes, e é essa separação que sustenta a automação:

| | Fundamentos | Mercado |
|---|---|---|
| Campos | receita, EBITDA, capex, dívida líquida, produção, margens, ROE/ROA | preço, market cap, P/E, dividend yield, EV/EBITDA |
| Muda quando | sai um balanço (trimestral) | todo pregão |
| Como atualiza | à mão, com fonte citada | rotina automática |

### Mercado — automático

O workflow `.github/workflows/atualiza-mercado.yml` roda de segunda a sexta às 22:00 UTC (depois do fechamento de NY), busca os dados no Yahoo Finance, regenera HTML e CSV, roda os testes e só então commita. Para rodar na mão: aba **Actions → Atualiza dados de mercado → Run workflow** (tem a opção *dry run*, que mostra o que mudaria sem commitar).

Localmente:

```bash
pip install -r requirements-market.txt
python3 update_market_data.py --dry-run     # simula
python3 update_market_data.py               # atualiza o JSON
```

A rotina é deliberadamente desconfiada da fonte:

- **Faixas de plausibilidade** por campo — um P/E de 5.000 ou um yield de 40% é descartado.
- **Limite de variação** por atualização (40% para preço e market cap, 70% para múltiplos). Um desdobramento de ações ou uma troca de símbolo produz um número que é válido isoladamente mas pula de patamar; o valor antigo é mantido e a rejeição fica registrada.
- **Fail-safe campo a campo** — o que não passa na validação não sobrescreve nada. Se um ticker não responde, o bloco inteiro dele fica intacto. A rotina só falha (e deixa o workflow vermelho) se *nenhum* ticker responder, o que indica que a fonte caiu ou mudou de formato.
- **Escrita cirúrgica** — o JSON é curado à mão, com objetos compactos de uma linha. Em vez de reserializar o arquivo (o que trocaria todas as linhas), a rotina substitui só os blocos `mercado` que mudaram: um commit diário mexe em ~8 linhas e o histórico continua legível.
- **Conferência pós-escrita** — o resultado é reparseado e comparado com o original para garantir que nenhum campo fundamental foi tocado.

Cada execução guarda um relatório JSON como artefato do Actions (30 dias) com tudo que mudou, foi rejeitado ou falhou. O resumo também vai no corpo da mensagem de commit.

> O dividend yield merece nota: o `yfinance` já devolveu esse campo como fração (`0.0278`) em algumas versões e como percentual (`2.78`) em outras — um erro silencioso de 100×. A rotina prefere calcular o yield a partir do dividendo anual e do preço, que não tem ambiguidade de unidade, e só recorre ao campo pronto como último recurso, desambiguando por magnitude.

### Fundamentos — à mão

1. Edite `indicadores_oleo_gas.json` (único arquivo de dados a editar manualmente).
2. Rode `python3 build_dashboard.py`.
3. Confira os avisos de validação impressos no terminal.
4. Rode `python3 -m pytest tests -q`.
5. Faça commit — o workflow `build-dashboard.yml` regenera HTML e CSV, e o GitHub Pages republica o site a partir da `main`.

## O que o dashboard faz

**Controles globais** (barra fixa no topo) — filtro por empresa, alternância FY2025 ↔ trimestre que afeta **todos** os gráficos, anualização do trimestre (×4) para comparação na mesma base, escala logarítmica, ordenação das barras e navegação entre seções.

**Seções**

| Seção | Conteúdo |
|---|---|
| Explorador de indicadores | Qualquer um dos 28 indicadores em colunas, barras horizontais ou participação, com leitura automática do melhor/pior/média |
| Resultado e geração de caixa | Receita, lucro líquido, EBITDA e FCF — ano fiscal vs. trimestre |
| Ponte de caixa | Waterfall da receita ao caixa livre por empresa, com o percentual da receita retido em cada etapa |
| Balanço e rentabilidade | Dívida líquida, ND/EBITDA, ROE vs. ROA, margem líquida vs. margem EBITDA |
| Eficiência operacional | Receita e EBITDA por boe, conversão de FCF, intensidade de reinvestimento, produção |
| Valuation | Bolhas EV/EBITDA × ROE (área = market cap), dividend yield × FCF yield com diagonal de cobertura, múltiplos, EV por boe/d |
| Perfil e ranking | Radar normalizado 0–100 em 6 eixos e matriz de ranking com heatmap |
| Séries históricas | Aparece automaticamente quando o campo `historico` do JSON é preenchido |
| Tabela completa | Todos os indicadores, ordenação por qualquer coluna, busca e alternância de derivados |

**Interações** — clicar numa barra isola a empresa (clicar de novo volta a todas), exportar PNG de qualquer gráfico, baixar o CSV da visão atual (respeitando filtros, período e anualização) e imprimir em PDF.

## Indicadores

**Primários** (direto da fonte): receita, lucro líquido, EBITDA, margem líquida, fluxo de caixa operacional, free cash flow, capex, dívida líquida, dívida/patrimônio, ROE, ROA, produção, market cap, P/E, EV/EBITDA, dividend yield e preço da ação.

**Derivados** (calculados em `build_dashboard.py`, nunca gravados no JSON):

| Indicador | Fórmula | Para que serve |
|---|---|---|
| Margem EBITDA | EBITDA ÷ receita | Rentabilidade operacional antes de estrutura de capital |
| ND / EBITDA | dívida líquida ÷ EBITDA anualizado | Alavancagem na medida usada por credores e agências |
| Conversão de FCF | FCF ÷ EBITDA | Quanto do lucro operacional realmente vira caixa |
| Capex / FCO | \|capex\| ÷ fluxo de caixa operacional | Intensidade de reinvestimento |
| Receita por boe | receita ÷ (produção × dias do período) | Preço realizado por barril (inflado por downstream) |
| EBITDA por boe | EBITDA ÷ (produção × dias do período) | Margem por barril — a leitura comparável entre pares |
| Enterprise value | market cap + dívida líquida | Valor da firma, neutro à estrutura de capital |
| EV por boe/d | EV ÷ produção diária | Quanto o mercado paga pela capacidade instalada |
| FCF yield | FCF anualizado ÷ market cap | Retorno de caixa implícito no preço |
| Cobertura do dividendo | FCF anualizado ÷ (market cap × dividend yield) | Se o dividendo cabe no caixa gerado |
| Run-rate do trimestre | (trimestre × 4 ÷ ano fiscal) − 1 | Aceleração ou desaceleração vs. o ano fiscal |

Os **scores do radar** normalizam seis eixos (rentabilidade, geração de caixa, solidez, valuation, retorno ao acionista e escala) de 0 a 100 por min-max entre as sete empresas — é uma leitura **relativa ao grupo**, não uma nota absoluta.

## Séries históricas (opcional)

O dashboard já suporta séries anuais. Basta preencher a lista `historico` de cada empresa no JSON:

```json
"historico": [
  {"periodo":"FY2021","receita":285640,"lucro_liquido":23040,"ebitda":51230,
   "fluxo_caixa_operacional":48130,"fcf":37970,"capex":-10160,
   "divida_liquida":43420,"producao_kboed":3700}
]
```

Campos ausentes viram `null` e são pulados nas linhas. Quando ao menos uma empresa tiver histórico, a seção "Séries históricas" aparece sozinha, com seletor de indicador.

## Validações automáticas

`build_dashboard.py` avisa (sem bloquear) sobre: lucro maior que receita, EBITDA fora de escala, margem EBITDA acima de 100%, ND/EBITDA acima de 4x, FCF que não cobre o dividendo estimado, produção ausente (uso de proxy), P/E negativo, empresa sem fontes e item de histórico sem `periodo`.

`tests/test_build.py` confere as fórmulas contra cálculos manuais, garante que o JSON primário não é contaminado pela camada derivada e que o HTML e o CSV publicados estão sincronizados com o template.

`tests/test_update_market.py` cobre a rotina de mercado sem tocar a rede: normalização de unidades, rejeição de valores absurdos, fail-safe por campo e por ticker, e a garantia de que a reescrita cirúrgica não corrompe nem desloca nada.

## Metodologia e fontes

- Fonte principal: [stockanalysis.com](https://stockanalysis.com), complementada por press releases oficiais (Shell, BP, Equinor, TotalEnergies) para dívida líquida/gearing e produção. Os dados de mercado passam a vir do Yahoo Finance a partir da automação diária.
- **Petrobras**: demonstrações originais em BRL, convertidas para USD com taxa média implícita (~R$5,58/US$ em FY2025; ~R$5,25/US$ em Q1 2026). Métricas de mercado já nativas em USD (ADR na NYSE).
- **BP/Shell**: dívida líquida e gearing na metodologia oficial (não-IFRS) de cada empresa.
- **BP FY2025**: lucro líquido atribuível próximo de zero (US$ 55 milhões) por itens não recorrentes.
- **Equinor e TotalEnergies**: caixa líquido positivo (dívida líquida negativa) nos dois períodos.
- **Equinor FY2025**: produção anual indisponível na fonte padronizada; os indicadores por boe do ano usam a produção do trimestre como proxy (sinalizado na validação).
- **Dividend yield da Petrobras**: ~5,34% (stockanalysis.com), mas varia de 5,3% a 9,3% entre fontes — tratar como faixa.
- **Anualização** do trimestre é uma simplificação: ignora sazonalidade, paradas de manutenção e capital de giro.

⚠️ Os dados de mercado são atualizados automaticamente todo dia útil (a data do último snapshot está no rodapé do dashboard). Os **fundamentos** continuam ancorados em FY2025 e Q1 2026 e só mudam quando sai um balanço novo — ou seja, múltiplos como P/E e EV/EBITDA combinam preço de hoje com lucro de ontem, que é como o mercado os calcula mesmo. Conteúdo informativo, não é recomendação de investimento.
