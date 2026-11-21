# Dashboard Financeiro — Óleo & Gás

Dashboard comparativo de **30 indicadores** financeiros, operacionais e de valuation — 16 primários e 14 derivados — de 7 grandes petroleiras: **ExxonMobil, Chevron, Shell, BP, Equinor, TotalEnergies e Petrobras**.

Períodos cobertos: o **último ano fiscal fechado de cada empresa** e o **trimestre mais recente de cada empresa**, com os trimestres anteriores na série histórica. As empresas divulgam em datas diferentes — e a Petrobras entra dias depois das outras, quando o portal da CVM é regenerado —, então durante a temporada de balanços a coluna do trimestre mistura períodos; o dashboard avisa quando isso acontece e mostra o trimestre de cada empresa sob o ticker. Este README não cita um trimestre de propósito: ele não é regenerado a cada balanço e envelheceria. Os fundamentos foram coletados em 20/07/2026 e revisados a cada balanço; a data do último snapshot de mercado está no rodapé do dashboard.

**Dashboard ao vivo (GitHub Pages):** https://jmagomez.github.io/oil-gas-financial-dashboard/

Os dados de mercado (cotação, market cap, P/E e dividend yield) são atualizados **automaticamente todo dia útil**, após o fechamento de Nova York.

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
- `coleta_cvm.py` — coleta da Petrobras direto do ITR/DFP da CVM, já convertida para dólar.
- `ptax.py` e `ptax/raw.txt` — PTAX do Banco Central (média e fechamento por trimestre) e a série diária que as gera.
- `brent.py` e `brent/raw.txt` — Brent médio por trimestre e por ano, da série mensal da EIA (versionada pelo mesmo motivo da PTAX).
- `escrita_cirurgica.py` — primitivas de escrita compartilhadas pelas duas rotinas acima: achar cada ticker no JSON, serializar um bloco em uma linha na ordem canônica, sincronizar `atualizado_em`. Existe para que o diff de uma atualização continue pequeno (algumas linhas, não o arquivo inteiro reformatado).
- `build_email.py` — corpo do e-mail diário com o retrato do fechamento.
- `requirements-market.txt` — dependência das rotinas de dados (`yfinance`).
- `CLAUDE.md` — briefing operacional para quem **edita** o código ou os dados: convenções, regras de negócio e a mecânica das rotinas. Este README cobre o que o dashboard mostra; o `CLAUDE.md` cobre como ele é mantido.
- `.github/actions/` — dois composite actions (`prepara-ambiente`, `publica-artefatos`) que concentram o gate `build → teste → commit` usado pelos três workflows que escrevem nos artefatos gerados.
- `tests/` — suíte `pytest`: fórmulas derivadas, base de 12 meses, histórico derivado, rotinas de mercado e de fundamentos, corpo do e-mail e camada de acessibilidade.

## Duas camadas de apresentação, por enquanto

O dashboard que está no ar é o `dashboard_oleo_gas.html`, gerado pelo pipeline
Python. Em paralelo, uma camada nova em React vive em [`app/`](app/README.md) e
migra as análises uma a uma — publicada em `/app` do mesmo site.

A convivência é deliberada: **nenhuma análise sai do ar antes de ter
substituto**. O motivo principal da reescrita é acessibilidade — o template
atual desenha os gráficos em 65 elementos `<canvas>`, que um leitor de tela não
consegue ler. A arquitetura e as decisões de interface estão no
[README do app](app/README.md); este arquivo continua sendo o lugar onde os
indicadores e as fontes são explicados.

## Como atualizar os dados

Os dados têm dois regimes, e é essa separação que sustenta a automação:

| | Fundamentos | Mercado |
|---|---|---|
| Campos | receita, EBITDA, capex, dívida líquida, produção, margens, ROE/ROA | preço, market cap, P/E, dividend yield |
| Muda quando | sai um balanço (trimestral) | todo pregão |
| Como atualiza | rotina mensal + revisão à mão, com fonte citada | rotina automática diária |

### Mercado — automático

O workflow `.github/workflows/atualiza-mercado.yml` roda de segunda a sexta às 22:00 UTC (depois do fechamento de NY), busca os dados no Yahoo Finance, regenera HTML e CSV, roda os testes e só então commita. Para rodar na mão: aba **Actions → Atualiza dados de mercado → Run workflow**, que tem a opção *dry run*.

```bash
pip install -r requirements-market.txt
python3 update_market_data.py --dry-run     # simula
python3 update_market_data.py               # atualiza o JSON
```

A rotina é deliberadamente desconfiada da fonte: valor fora de faixa de plausibilidade ou com salto de patamar não sobrescreve nada, o valor curado é mantido e a rejeição fica registrada no relatório da execução (artefato do Actions, 30 dias). Ela só falha de verdade se *nenhum* ticker responder. **A mecânica — quais faixas, quais limites, por que a escrita no JSON é cirúrgica e como o dividend yield é desambiguado — está em [`CLAUDE.md`](CLAUDE.md).**

### Fundamentos — rotina mensal, revisão à mão

O workflow `atualiza-fundamentos.yml` roda no dia 5 de cada mês — seis empresas pelo Yahoo, a Petrobras pela CVM com conversão por PTAX — e **só age em trimestre novo**: se a fonte devolve o mesmo trimestre que já está no arquivo, nada é tocado, e divergência acima de 5% vira aviso. Antes de gravar, confere **coerência entre as demonstrações** (FCF = FCO + capex, EBITDA ≤ receita, margem batendo com lucro/receita), não só faixa por campo — um número plausível no campo errado passa na faixa mas não na identidade contábil. O disparo manual vem com *simular* marcado por padrão.

Para editar à mão:

1. Edite `indicadores_oleo_gas.json` (único arquivo de dados a editar manualmente).
2. Rode `python3 build_dashboard.py` e confira os avisos de validação impressos.
3. Rode `python3 -m pytest`.
4. Faça commit — `build-dashboard.yml` regenera HTML e CSV, e o GitHub Pages republica a partir da `main`.

## O que o dashboard faz

**Controles globais** (barra fixa no topo) — filtro por empresa, alternância ano fiscal ↔ trimestre que afeta **todos** os gráficos, base de 12 meses (TTM) para comparação na mesma base, escala logarítmica, ordenação das barras e navegação entre seções.

**Seções**

| Seção | Conteúdo |
|---|---|
| Explorador de indicadores | Qualquer um dos 30 indicadores em colunas, barras horizontais ou participação, com leitura automática do melhor/pior/média |
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

**Primários** (direto da fonte): receita, lucro líquido, EBITDA, margem líquida, fluxo de caixa operacional, free cash flow, capex, dívida líquida, dívida/patrimônio, ROE, ROA, produção, market cap, P/E, dividend yield e preço da ação. O **EV/EBITDA saiu desta lista**: deixou de ser lido da fonte e passou a ser derivado de `ev ÷ EBITDA`.

**Derivados** (calculados em `build_dashboard.py`, nunca gravados no JSON):

| Indicador | Fórmula | Para que serve |
|---|---|---|
| Margem EBITDA | EBITDA ÷ receita | Rentabilidade operacional antes de estrutura de capital |
| ND / EBITDA | dívida líquida ÷ EBITDA dos últimos 12 meses (TTM) | Alavancagem na medida usada por credores e agências |
| Conversão de FCF | FCF ÷ EBITDA | Quanto do lucro operacional realmente vira caixa |
| Capex / FCO | \|capex\| ÷ fluxo de caixa operacional | Intensidade de reinvestimento |
| Receita por boe | receita ÷ (produção × dias do período) | Preço realizado por barril (inflado por downstream) |
| EBITDA por boe | EBITDA ÷ (produção × dias do período) | Margem por barril — a leitura comparável entre pares |
| Enterprise value | market cap + dívida líquida + não controladores | Valor da firma, neutro à estrutura de capital. Os não controladores entram porque o EBITDA é consolidado a 100% — na BP são ~16% do market cap. `derivados.ev_inclui_nao_controladores` diz se o saldo estava disponível |
| EV / EBITDA | EV ÷ EBITDA dos últimos 12 meses (TTM) | Múltiplo de valuation neutro à estrutura de capital. **Calculado aqui, não lido do Yahoo**: o `enterpriseToEbitda` da fonte usa outro numerador e outro denominador, e as duas definições divergiam de +6% a +100% sob o mesmo rótulo. Mesma base de 12 meses do ND / EBITDA |
| EV por boe/d | EV ÷ produção diária | Quanto o mercado paga pela capacidade instalada |
| FCF yield | FCF dos últimos 12 meses (TTM) ÷ market cap | Retorno de caixa implícito no preço |
| Dividend yield (caixa) | dividendos **pagos** em 12 meses (DFC) ÷ market cap | Yield sem razão de ADR: totais da companhia sobre o market cap da companhia. O yield de mercado da Shell vinha 2× menor (dividendo por ação ordinária sobre o preço do ADS, que vale duas) |
| Shareholder yield | (dividendos + recompras pagos em 12 meses) ÷ market cap | O retorno em caixa que as majors entregam de fato — Shell, XOM e CVX devolvem a maior parte por recompra |
| Distribuição / FCO | (dividendos + recompras **pagos** em 12 meses) ÷ FCO de 12 meses | Perto da métrica que as companhias guiam, mas **não é a mesma conta**: a Shell guia 40–50% do CFFO **no ciclo** e conta a recompra **anunciada**. Com recompra em valor fixo por trimestre, um ano de petróleo caro derruba o percentual pago sem que a política mude — não leia a diferença como corte |
| Concentração de recompras | maior trimestre de recompra ÷ recompras de 12 meses | Acima de 50%, o shareholder yield é pico, não ritmo. Caso típico: a Equinor recompra a fatia do Estado norueguês de uma vez, após a assembleia de maio; o cartão marca com `*` |
| Brent médio | média mensal da EIA no trimestre da empresa (ou no ano) | Contexto de preço: separa o que é petróleo do que é desempenho. Preço realizado por empresa não entra — as sete o definem de jeitos diferentes |
| Cobertura do dividendo | FCF dos últimos 12 meses (TTM) ÷ (market cap × dividend yield) | Se o dividendo cabe no caixa gerado. O payout sobre FCF é `100 ÷ cobertura` e não existe como indicador próprio — seria a mesma informação em duas colunas |
| Run-rate do trimestre | (trimestre × 4 ÷ ano fiscal) − 1 | Aceleração ou desaceleração vs. o ano fiscal |

### Base de 12 meses, não trimestre × 4

Os indicadores que dividem um fluxo por um estoque ou por market cap (ND/EBITDA, FCF yield, cobertura de dividendo) usam a **soma dos quatro últimos trimestres**. Multiplicar um trimestre por 4 extrapola aquele trimestre para o ano inteiro, e num setor cujo resultado acompanha o preço da commodity isso distorce muito: medido nos dados do 2T26 — um trimestre de pico —, o ×4 inflava o FCF yield entre 54% e 176% e subestimava a alavancagem entre 8% e 40%, sempre na direção que faz a empresa parecer melhor.

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

A coleta de fundamentos **bloqueia**, descartando a empresa inteira: demonstrações em moeda diferente de USD (`financialCurrency`, que é a moeda do balanço — não `currency`, que é a da cotação) e salto de receita acima de 2,5× contra o trimestre curado. A segunda existe porque a primeira depende de um metadado: se a fonte deixar de informá-lo, a guarda pararia de guardar sem avisar. As identidades contábeis não cobrem esse caso — todas são invariantes a escala, e um balanço inteiro em BRL passa em todas.

A suíte `pytest` cobre as fórmulas derivadas contra cálculos manuais, a base de 12 meses e seu fallback, os derivados do histórico, as duas rotinas de coleta sem tocar a rede, o corpo do e-mail e a camada de acessibilidade. Cada defeito já corrigido tem um teste que o nomeia.

Os testes de lógica leem `tests/fixtures/indicadores_snapshot.json`, um snapshot congelado — não o arquivo vivo. Assertar sobre o arquivo vivo faria a própria atualização dos dados quebrar a suíte, e a trava "roda os testes antes de commitar" passaria a impedir para sempre o commit que ela deveria proteger. O contrato de **formato** do arquivo vivo continua testado, em `test_update_market.test_formato_do_arquivo_vivo_suporta_escrita_cirurgica`.

## Metodologia e fontes

- Fonte principal: [stockanalysis.com](https://stockanalysis.com), complementada por press releases oficiais (Shell, BP, Equinor, TotalEnergies) para dívida líquida/gearing e produção. Os dados de mercado passam a vir do Yahoo Finance a partir da automação diária.
- **Petrobras**: publica em reais; é coletada do ITR/DFP consolidado da **CVM** e convertida pela **PTAX** do Banco Central — fluxos (receita, lucro, EBITDA, FCO, capex) pela média do trimestre, saldos (dívida, caixa, patrimônio, ativos) pelo fechamento do último dia útil. É a regra que reproduz o que a companhia divulga em dólar: a dívida líquida convertida bate com a do release em seis trimestres seguidos, dentro de 0,5%. As taxas usadas ficam gravadas em `proveniencia.fundamentos.conversao`, e a série diária em `ptax/raw.txt`. O **EBITDA** é o da Resolução CVM 156 (LAIR − resultado financeiro + D&A); a série trimestral 2T25–2T26 foi rebaseada para essa definição, que diverge da do agregador em até 27% por trimestre. FY2025 e os demais campos dos trimestres anteriores ao 3T26 vêm da curadoria original, que difere da conversão por PTAX em menos de 1%. Métricas de mercado já nativas em USD (ADR na NYSE).
- **Dívida líquida em uma definição só**: dívida bruta com arrendamentos − caixa e aplicações de curto prazo, para as sete e para todos os períodos; o ano fiscal usa o saldo do 4T. Não é o número que cada empresa destaca (a BP divulga sem arrendamentos e sem híbridos), e é por isso que compara. Até 11/2026 o FY2025 de BP e Shell vinha na metodologia de cada uma.
- **BP FY2025**: lucro líquido atribuível próximo de zero (US$ 55 milhões) por itens não recorrentes.
- **Correção (11/2026)**: Equinor e TotalEnergies apareciam em caixa líquido no FY2025 e no 1T26. Era sinal trocado (convenção "Net Cash (Debt)" de agregador) — a TotalEnergies reporta gearing de 15%. O build agora acusa troca de sinal grande entre trimestres.
- **Recompras da BP**: da DFC do release do 3T26 — 750 no 3T25, 562 no 1T26, zero no 2T26 e no 3T26 (o caixa excedente foi para a dívida). O Yahoo omite a linha quando ela é zero.
- **Recompras da Petrobras**: zero, porque a DFC entregue à CVM não tem linha de recompra; o último programa (2023–2024) foi encerrado. As linhas de financiamento lidas saem no resumo de cada coleta.
- **Ano fiscal de cada empresa**: o bloco `anual` traz o ano dentro (`anual.ano`). Quando o 4T de um ano novo chega e os quatro trimestres estão no arquivo, a rotina de fundamentos vira o ano sozinha — fluxos somados, saldos do 4T — e registra em `proveniencia.anual`. Se o ano não virar, o build avisa.
- **Equinor FY2025**: produção anual indisponível na fonte padronizada; os indicadores por boe do ano usam a produção do trimestre como proxy (sinalizado na validação).
- **Remuneração ao acionista em caixa**: dividendos e recompras saem da DFC de cada trimestre (Yahoo para seis empresas; CVM para a Petrobras, convertida pela PTAX média) e somam em 12 meses. O eixo "Retorno ao acionista" do radar usa **shareholder yield** quando as sete o têm; se faltar para alguma, cai para o dividend yield de caixa e, em último caso, para o de mercado — sempre a mesma base para o grupo inteiro, e o radar diz qual. O yield de mercado continua no painel como referência, e o build acusa quando ele diverge do caixa pago por mais de 35% (a assinatura da razão de ADR).
- **Dividend yield da Petrobras**: ~5,34% (stockanalysis.com), mas varia de 5,3% a 9,3% entre fontes — tratar como faixa.
- **Shell**: a empresa publica duas bases de produção. A coluna anual usa o total do grupo (FY2025 = 2.800 mil boe/d); a série trimestral usa a soma de Upstream + Integrated Gas (2.759 no mesmo ano). As duas divergem ~1,5% e estão em bases diferentes — divergência preexistente, registrada nas notas do JSON.
- **ROE e ROA**: no trimestre são lucro dos últimos 12 meses ÷ patrimônio (ou ativos) do **fim** do período; no ano fiscal vêm da fonte padronizada, em base própria. **As duas colunas não são comparáveis entre si** — a diferença entre períodos não é variação real.
- **Margem líquida**: a exibida é sempre `lucro_liquido ÷ receita`, recalculada dos campos gravados. A fonte calcula sobre o lucro **consolidado** (com não-controladores) e o campo `lucro_liquido` traz a parcela **atribuível aos acionistas** — na BP de FY2025 a diferença é entre 0,68% e 0,03%. O valor original fica em `margem_liquida_fonte_pct` e a divergência vira aviso de validação.
- **Trimestre de cada empresa, não do conjunto**: não existe "o trimestre do dashboard". Cada empresa está no trimestre mais recente que ela divulgou, e o resumo do conjunto (`meta_build.trimestre_recente`) é derivado no build a partir disso — nunca armazenado. Quando as sete estão no mesmo trimestre, ele aparece no cabeçalho e no botão de período; quando não estão, o botão vira "Último trimestre", aparece um aviso sob a barra de controles, cada barra traz o trimestre sob o ticker (ex.: `XOM / 4T26`) e cada linha do CSV exportado leva o trimestre da própria empresa.
- **Produção**: não sai de demonstração financeira, e sim dos relatórios de produção. A rotina automática carrega o valor do trimestre anterior e marca isso em `proveniencia`; a atualização é manual, rastreada release por release. **Enquanto a produção não é atualizada, o denominador dos indicadores por barril fica um trimestre atrás do numerador** — e agora isso aparece na tela: `derivados.producao_defasada` dispara um aviso no painel de eficiência, dizendo de que trimestre veio a produção. Não confundir com `producao_proxy`, que marca ausência total.
- **Produção do 3T26** (cada número conferido contra o trimestre anterior já presente no JSON antes de ser aceito): ExxonMobil 4.496 koebd, Chevron 3.980 MBOED, Shell 2.574 (Upstream 1.802 + Integrated Gas 772), BP 2.220, Equinor 2.166, TotalEnergies 2.474 (E&P 1.963 + GNL integrado 511), Petrobras 3.512 (produção própria, não a operada de 5,08 MMboed). O salto do Integrated Gas da Shell (631 → 772) é a aquisição da ARC Resources, não crescimento orgânico.

⚠️ Os dados de mercado são atualizados automaticamente todo dia útil (a data do último snapshot está no rodapé do dashboard). Os **fundamentos** continuam ancorados no último ano fiscal e no trimestre mais recente **de cada empresa** — que nem sempre é o mesmo — e só mudam quando sai um balanço novo — ou seja, múltiplos como P/E e EV/EBITDA combinam preço de hoje com lucro de ontem (no EV/EBITDA, com o EBITDA de 12 meses do próprio payload), que é como o mercado os calcula mesmo. Conteúdo informativo, não é recomendação de investimento.
