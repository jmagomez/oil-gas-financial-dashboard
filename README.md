# Dashboard Financeiro — Óleo & Gás

Dashboard comparativo de **28 indicadores** financeiros, operacionais e de valuation — 17 primários e 11 derivados — de 7 grandes petroleiras: **ExxonMobil, Chevron, Shell, BP, Equinor, TotalEnergies e Petrobras**.

Períodos cobertos: ano fiscal **FY2025** (encerrado em 31/12/2025) e o trimestre mais recente divulgado, **Q2 2026** (encerrado em 30/06/2026), com os quatro trimestres anteriores na série histórica. Os fundamentos foram coletados em 20/07/2026 e revisados a cada balanço; a data do último snapshot de mercado está no rodapé do dashboard.

**Dashboard ao vivo (GitHub Pages):** https://jmagomez.github.io/oil-gas-financial-dashboard/

Os dados de mercado (cotação, market cap, P/E, dividend yield e EV/EBITDA) são atualizados **automaticamente todo dia útil**, após o fechamento de Nova York.

## Arquivos

- `dashboard_oleo_gas.html` — dashboard interativo, **gerado automaticamente** (não editar à mão).
- `index.html` — página de entrada do GitHub Pages; só encaminha para o dashboard.
- `dashboard_template.html` — esqueleto do dashboard (HTML/CSS/JS), com o placeholder `__DATA_JSON__`.
- `assets_a11y.css` / `assets_a11y.js` — camada de acessibilidade e usabilidade, embutida no HTML pelo build. Os gráficos são `<canvas>` e seriam invisíveis para leitor de tela sem ela.
- `indicadores_oleo_gas.json` — **fonte única de verdade**: apenas dados primários, notas metodológicas e fontes. Nenhum indicador derivado é gravado aqui.
- `indicadores_oleo_gas.csv` — mesma base em formato tabular (uma linha por empresa/período), agora com as colunas derivadas.
- `build_dashboard.py` — calcula os derivados, valida os números e gera o HTML e o CSV.
- `update_market_data.py` — rotina que atualiza só os dados de mercado (ver abaixo).
- `update_fundamentals.py` — rotina que rotaciona o trimestre quando sai um balanço novo.
- `escrita_cirurgica.py` — primitivas de escrita compartilhadas pelas duas rotinas acima: achar cada ticker no JSON, serializar um bloco em uma linha na ordem canônica, sincronizar `atualizado_em`. Existe para que o diff de uma atualização continue pequeno (algumas linhas, não o arquivo inteiro reformatado).
- `build_email.py` — corpo do e-mail diário com o retrato do fechamento.
- `requirements-market.txt` — dependência das rotinas de dados (`yfinance`).
- `tests/` — suíte `pytest`: fórmulas derivadas, base de 12 meses, histórico derivado, rotinas de mercado e de fundamentos, corpo do e-mail e camada de acessibilidade.

## Como atualizar os dados

Os dados têm dois regimes, e é essa separação que sustenta a automação:

| | Fundamentos | Mercado |
|---|---|---|
| Campos | receita, EBITDA, capex, dívida líquida, produção, margens, ROE/ROA | preço, market cap, P/E, dividend yield, EV/EBITDA |
| Muda quando | sai um balanço (trimestral) | todo pregão |
| Como atualiza | rotina mensal + revisão à mão, com fonte citada | rotina automática diária |

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

### Fundamentos — rotina mensal, revisão à mão

O workflow `atualiza-fundamentos.yml` roda no dia 5 de cada mês e **só age em trimestre novo**: se a fonte devolve o mesmo trimestre que já está no arquivo, nada é tocado — dado curado não é sobrescrito em silêncio, e divergência acima de 5% vira aviso no relatório. O disparo manual vem com *simular* marcado por padrão.

Antes de gravar, a rotina confere **coerência entre as demonstrações** (FCF = FCO + capex, EBITDA ≤ receita, margem batendo com lucro/receita), não só faixa por campo: um número plausível no campo errado passa em validação de faixa mas não em identidade contábil. Coerência quebrada descarta a empresa inteira — meio balanço errado é pior que nenhum.

Para editar à mão:

1. Edite `indicadores_oleo_gas.json` (único arquivo de dados a editar manualmente).
2. Rode `python3 build_dashboard.py`.
3. Confira os avisos de validação impressos no terminal.
4. Rode `python3 -m pytest tests -q`.
5. Faça commit — o workflow `build-dashboard.yml` regenera HTML e CSV, e o GitHub Pages republica o site a partir da `main`.

## O que o dashboard faz

**Controles globais** (barra fixa no topo) — filtro por empresa, alternância FY2025 ↔ trimestre que afeta **todos** os gráficos, base de 12 meses (TTM) para comparação na mesma base, escala logarítmica, ordenação das barras e navegação entre seções.

**Seções**

| Seção | Conteúdo |
|---|---|
| Explorador de indicadores | Qualquer um dos 28 indicadores em colunas, barras horizontais ou participação, com leitura automática do melhor/pior/média |
| Resultado e geração de caixa | Receita, lucro líquido, EBITDA e FCF — ano fiscal vs. trimestre |
| Ponte de caixa | Waterfall da receita ao caixa livre por empresa, com o percentual da receita retido em cada etapa |
| Balanço e rentabilidade | Dívida líquida, ND/EBITDA, ROE vs. ROA, margem líquida vs. margem EBITDA |
| Eficiência operacional | Receita e EBITDA por boe, conversão de FCF, intensidade de reinvestimento, produção |
| Valuation | Bolhas EV/EBITDA × ROE (área = market cap), dividend yield × FCF yield com diagonal de cobertura, múltiplos, EV por boe/d |
| Perfil e ranking | Radar de **posição relativa** em 6 eixos (ver ressalva abaixo) e matriz de ranking com heatmap |
| Séries históricas | Evolução trimestre a trimestre, dos valores absolutos **e dos derivados de cada período** |
| Tabela completa | Todos os indicadores, ordenação por qualquer coluna, busca e alternância de derivados |

**Interações** — clicar numa barra isola a empresa (clicar de novo volta a todas), exportar PNG de qualquer gráfico, baixar o CSV da visão atual (respeitando filtros, período e base de 12 meses) e imprimir em PDF.

## Indicadores

**Primários** (direto da fonte): receita, lucro líquido, EBITDA, margem líquida, fluxo de caixa operacional, free cash flow, capex, dívida líquida, dívida/patrimônio, ROE, ROA, produção, market cap, P/E, EV/EBITDA, dividend yield e preço da ação.

**Derivados** (calculados em `build_dashboard.py`, nunca gravados no JSON):

| Indicador | Fórmula | Para que serve |
|---|---|---|
| Margem EBITDA | EBITDA ÷ receita | Rentabilidade operacional antes de estrutura de capital |
| ND / EBITDA | dívida líquida ÷ EBITDA dos últimos 12 meses (TTM) | Alavancagem na medida usada por credores e agências |
| Conversão de FCF | FCF ÷ EBITDA | Quanto do lucro operacional realmente vira caixa |
| Capex / FCO | \|capex\| ÷ fluxo de caixa operacional | Intensidade de reinvestimento |
| Receita por boe | receita ÷ (produção × dias do período) | Preço realizado por barril (inflado por downstream) |
| EBITDA por boe | EBITDA ÷ (produção × dias do período) | Margem por barril — a leitura comparável entre pares |
| Enterprise value | market cap + dívida líquida | Valor da firma, neutro à estrutura de capital |
| EV por boe/d | EV ÷ produção diária | Quanto o mercado paga pela capacidade instalada |
| FCF yield | FCF dos últimos 12 meses (TTM) ÷ market cap | Retorno de caixa implícito no preço |
| Cobertura do dividendo | FCF dos últimos 12 meses (TTM) ÷ (market cap × dividend yield) | Se o dividendo cabe no caixa gerado |
| Run-rate do trimestre | (trimestre × 4 ÷ ano fiscal) − 1 | Aceleração ou desaceleração vs. o ano fiscal |

### Base de 12 meses, não trimestre × 4

Os indicadores que dividem um fluxo por um estoque ou por market cap (ND/EBITDA, FCF yield, cobertura de dividendo, payout) usam a **soma dos quatro últimos trimestres**. Multiplicar um trimestre por 4 extrapola aquele trimestre para o ano inteiro, e num setor cujo resultado acompanha o preço da commodity isso distorce muito: medido nos dados do 2T26 — um trimestre de pico —, o ×4 inflava o FCF yield entre 54% e 176% e subestimava a alavancagem entre 8% e 40%, sempre na direção que faz a empresa parecer melhor.

O ×4 sobrevive em dois lugares, de propósito: como **fallback declarado** quando a empresa não tem os quatro trimestres (o payload registra em `base_12m_ebitda` qual base gerou cada número, e o rótulo do gráfico avisa), e no **run-rate**, onde o ×4 *é* a definição do indicador.

Só **fluxo** acumula no TTM. Dívida líquida e patrimônio são estoque e não entram na soma — somar saldo de balanço ao longo de quatro trimestres não significa nada. Produção entra como **média**, por ser taxa por dia.

### Tendência, não só nível

A série histórica carrega os derivados calculados para **cada** trimestre — margem EBITDA e líquida, conversão de FCF, capex/FCO e os US$/boe —, não apenas os valores absolutos. Num setor cíclico é a tendência que separa oscilação de preço de erosão estrutural: nos dados atuais a margem EBITDA da ExxonMobil cai de 21,3% para 14,5% entre o 2T25 e o 1T26 enquanto o capex/FCO sobe de 54% para 74%, e só então o 2T26 reverte.

ND/EBITDA e FCF yield **não** entram na série: precisam de TTM móvel e, com quatro trimestres de histórico, existiriam para um único ponto.

### Ressalva sobre os scores do radar

Os seis eixos (rentabilidade, geração de caixa, solidez, valuation, retorno ao acionista e escala) são normalizados de 0 a 100 por min-max entre as sete empresas, com a escala fixada no build. É leitura de **posição relativa, não de magnitude**: o melhor do grupo recebe 100 e o pior 0 em todo eixo, com dispersão real de 2x ou de 5x. Serve para comparar o *formato* de dois perfis, não para medir distância — para magnitude, use o explorador ou a tabela.

## Séries históricas

A seção aparece sozinha quando ao menos uma empresa tem a lista `historico` preenchida. Cada item é um **trimestre**, com rótulo `AAAA-QN` para ordenar cronologicamente como texto:

```json
"historico": [
  {"periodo":"2026-Q1","receita":83160,"lucro_liquido":4470,"ebitda":12060,
   "fluxo_caixa_operacional":8710,"fcf":2240,"capex":-6470,
   "divida_liquida":39230,"producao_kboed":4590}
]
```

O `build_dashboard.py` calcula os derivados de cada trimestre a partir desses campos e publica em `meta_build.derivados_historico` a lista do que ficou disponível — o seletor do gráfico é montado dessa lista, não de uma lista fixa no template.

Campos ausentes viram `null` e são pulados nas linhas. Métricas com cobertura esparsa aparecem marcadas no seletor ("parcial: 7 de 28"), com aviso sob o gráfico explicando de onde vem a lacuna — a marcação é medida dos dados e desaparece sozinha quando a série é preenchida.

## Validações automáticas

`build_dashboard.py` avisa (sem bloquear) sobre: lucro maior que receita, EBITDA fora de escala, margem EBITDA acima de 100%, ND/EBITDA acima de 4x, FCF que não cobre o dividendo estimado, produção ausente (uso de proxy), P/E negativo, empresa sem fontes e item de histórico sem `periodo`.

A suíte `pytest` cobre: fórmulas derivadas contra cálculos manuais, a base de 12 meses e seu fallback, os derivados do histórico, a rotina de mercado sem tocar a rede (unidades, rejeição de absurdos, fail-safe por campo e por ticker, escrita cirúrgica), a rotina de fundamentos contra números conferidos à mão, o corpo do e-mail e a camada de acessibilidade.

Os testes de lógica leem `tests/fixtures/indicadores_snapshot.json`, um snapshot congelado — não o arquivo vivo. Assertar sobre o arquivo vivo faria a própria atualização dos dados quebrar a suíte, e a trava "roda os testes antes de commitar" passaria a impedir para sempre o commit que ela deveria proteger. O contrato de **formato** do arquivo vivo continua testado, em `test_update_market.test_formato_do_arquivo_vivo_suporta_escrita_cirurgica`.

## Metodologia e fontes

- Fonte principal: [stockanalysis.com](https://stockanalysis.com), complementada por press releases oficiais (Shell, BP, Equinor, TotalEnergies) para dívida líquida/gearing e produção. Os dados de mercado passam a vir do Yahoo Finance a partir da automação diária.
- **Petrobras**: demonstrações originais em BRL, convertidas para USD. FY2025 e Q1 2026 usam taxa média implícita curada (~R$5,58 e ~R$5,25/US$); o Q2 2026 veio da fonte já em USD, a ~R$5,04/US$ implícito — conferido em duas linhas independentes (receita de R$ 169,53 bi e lucro de R$ 52,44 bi). Métricas de mercado já nativas em USD (ADR na NYSE).
- **BP/Shell**: dívida líquida e gearing na metodologia oficial (não-IFRS) de cada empresa.
- **BP FY2025**: lucro líquido atribuível próximo de zero (US$ 55 milhões) por itens não recorrentes.
- **Equinor e TotalEnergies**: caixa líquido positivo (dívida líquida negativa) nos dois períodos.
- **Equinor FY2025**: produção anual indisponível na fonte padronizada; os indicadores por boe do ano usam a produção do trimestre como proxy (sinalizado na validação).
- **Dividend yield da Petrobras**: ~5,34% (stockanalysis.com), mas varia de 5,3% a 9,3% entre fontes — tratar como faixa.
- **Shell**: a empresa publica duas bases de produção. A coluna anual usa o total do grupo (FY2025 = 2.800 mil boe/d); a série trimestral usa a soma de Upstream + Integrated Gas (2.759 no mesmo ano). As duas divergem ~1,5% e estão em bases diferentes — divergência preexistente, registrada nas notas do JSON.
- **ROE e ROA**: no trimestre são lucro dos últimos 12 meses ÷ patrimônio (ou ativos) do **fim** do período; no ano fiscal vêm da fonte padronizada, em base própria. **As duas colunas não são comparáveis entre si** — a diferença entre períodos não é variação real.
- **Margem líquida**: a exibida é sempre `lucro_liquido ÷ receita`, recalculada dos campos gravados. A fonte calcula sobre o lucro **consolidado** (com não-controladores) e o campo `lucro_liquido` traz a parcela **atribuível aos acionistas** — na BP de FY2025 a diferença é entre 0,68% e 0,03%. O valor original fica em `margem_liquida_fonte_pct` e a divergência vira aviso de validação.
- **Produção**: não sai de demonstração financeira, e sim dos relatórios de produção. A rotina automática carrega o valor do trimestre anterior e marca isso em `proveniencia`; a atualização é manual, rastreada release por release.

⚠️ Os dados de mercado são atualizados automaticamente todo dia útil (a data do último snapshot está no rodapé do dashboard). Os **fundamentos** continuam ancorados em FY2025 e Q2 2026 e só mudam quando sai um balanço novo — ou seja, múltiplos como P/E e EV/EBITDA combinam preço de hoje com lucro de ontem, que é como o mercado os calcula mesmo. Conteúdo informativo, não é recomendação de investimento.
