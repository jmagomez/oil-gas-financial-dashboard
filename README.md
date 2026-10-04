# Dashboard Financeiro — Óleo & Gás

Dashboard comparativo de **28 indicadores** financeiros, operacionais e de valuation — 17 primários e 11 derivados — de 7 grandes petroleiras: **ExxonMobil, Chevron, Shell, BP, Equinor, TotalEnergies e Petrobras**.

Períodos cobertos: ano fiscal **FY2025** (encerrado em 31/12/2025), o trimestre mais recente divulgado, **2T26 / Q2 2026** (encerrado em 30/06/2026), e a série trimestral **1T25–2T26** (seis trimestres). Fundamentos trimestrais coletados em 13/08/2026; 1T25 e correções em 02/10/2026 (versão de dados 1.3).

**Novo — PoC de benchmarking trimestral** (`poc/`): Petrobras vs. ExxonMobil, Shell e Equinor (escalável às 7), 6 indicadores × 6 trimestres, com controle de qualidade por registro (regras R1–R8), painel HTML autocontido e projeto Power BI (`powerbi/`). Ver a seção [PoC de benchmarking trimestral](#poc-de-benchmarking-trimestral).

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
- `poc/` — PoC de benchmarking trimestral (build, template do painel, catálogo de fontes, saídas geradas).
- `powerbi/gera_pbip.py` — gera o projeto Power BI (PBIP) da PoC.
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
| ND / EBITDA | dívida líquida ÷ EBITDA de 12 meses (FY no ano; TTM no trimestre, ×4 só sem janela de 4 trimestres) | Alavancagem na medida usada por credores e agências |
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

## Séries históricas

A lista `historico` de cada empresa guarda os trimestres anteriores ao `q_recente` (hoje 1T25 a 1T26), do mais antigo ao mais recente. `update_fundamentals.py` move o trimestre corrente para o fim da lista quando sai um balanço novo; o TTM usa os 3 últimos itens + `q_recente`.

```json
"historico": [
  {"periodo":"2025-Q1","receita":81058,"lucro_liquido":7713,"ebitda":17507,
   "fluxo_caixa_operacional":12953,"fcf":7055,"capex":-5898,
   "divida_liquida":20515,"producao_kboed":4551,"fonte_dado":"release 1T25 (primária)"}
]
```

O campo opcional `fonte_dado` registra a origem ou a correção de um item. Campos ausentes viram `null` e são pulados nas linhas.

## Validações automáticas

`build_dashboard.py` avisa (sem bloquear) sobre: lucro maior que receita, EBITDA fora de escala, margem EBITDA acima de 100%, ND/EBITDA acima de 4x, FCF que não cobre o dividendo estimado, produção ausente (uso de proxy), P/E negativo, empresa sem fontes e item de histórico sem `periodo`.

`tests/test_build.py` confere as fórmulas contra cálculos manuais, garante que o JSON primário não é contaminado pela camada derivada e que o HTML e o CSV publicados estão sincronizados com o template.

`tests/test_update_market.py` cobre a rotina de mercado sem tocar a rede: normalização de unidades, rejeição de valores absurdos, fail-safe por campo e por ticker, e a garantia de que a reescrita cirúrgica não corrompe nem desloca nada.

## PoC de benchmarking trimestral

Produto analítico trimestral que compara a Petrobras com pares usando só informação pública.

| | |
|---|---|
| Empresas | Petrobras + ExxonMobil, Shell, Equinor (seletor "Escala" liga Chevron, BP e TotalEnergies) |
| Indicadores | margem EBITDA, margem líquida, FCF, dívida líquida/EBITDA (TTM), EBITDA por boe, total de efetivo (+ EBITDA TTM por empregado, complementar) |
| Trimestres | 1T25 a 2T26 |
| Saídas | `poc/painel_benchmarking_poc.html`, `poc/fato_indicador.csv` (tabela longa), `poc/dim_*.csv`, `poc/qa_log.csv`, projeto Power BI em `powerbi/` |

```bash
python3 poc/build_poc.py                     # QA + indicadores + painel + CSVs
python3 poc/build_poc.py --check             # falha se houver vermelho no recorte da PoC
python3 poc/build_poc.py --json outra.json --evidencia qa.csv   # audita outra versão dos dados
python3 powerbi/gera_pbip.py                 # projeto Power BI lendo os CSVs deste repositório
python3 powerbi/gera_pbip.py --embutido      # projeto Power BI com dados embutidos (offline)
```

**Qualidade (R1–R8).** Completude, coerência contábil (FCF = FCO + capex; EBITDA ≤ receita), plausibilidade, desvio histórico (receita ±30%, EBITDA ±40%, lucro ±60%, margem ±15 p.p.; dívida por materialidade frente ao EBITDA anualizado; FCF com variação acima de 50% do EBITDA do trimestre anterior), contexto de mercado (desvio só é justificado se tiver a direção do Brent e até 3× a variação dele), revisão de dado já publicado, proveniência e reconciliação entre fontes. Cada valor recebe um selo (validado / ressalva / em análise) que herda o pior status dos insumos; valores "em análise" saem de rankings e medianas. Rodadas sobre a versão 1.2 dos dados, as regras encontraram 6 valores vermelhos (dívida líquida de Equinor, TotalEnergies e BP), corrigidos na 1.3 — evidência em `poc/evidencia_qa_v12.json`.

**Power BI.** `python3 powerbi/gera_pbip.py` gera `powerbi/projeto/Benchmarking_Petrobras_Pares.pbip` (relatório PBIR + modelo `model.bim`; 5 páginas, abre no trimestre mais recente e no universo da PoC). O parâmetro `UrlBase` aponta para os CSVs de `poc/` neste repositório. O log de QA traz a leitura de release e o link de cada alerta explicado. Se o Desktop oferecer converter o modelo para TMDL, escolha "Não atualizar" (o gerador trabalha com `model.bim`).

**Atualização trimestral do Power BI sem abrir o Desktop.** O cache de dados (`cache.abf`) só é gravado pelo Power BI, então o CI não consegue entregar um .pbix preenchido. A rotina que dispensa o passo manual é publicar uma vez no serviço:

1. Abra `powerbi/projeto/*.pbip` (versão do repositório, que lê os CSVs pela URL), clique em Atualizar e publique no workspace (Arquivo → Publicar).
2. No serviço: conjunto de dados → Configurações → Credenciais da fonte de dados → Web, autenticação **Anônima**, nível de privacidade **Público** (exige repositório público; para repositório privado use um gateway ou uma pasta do SharePoint/OneDrive como `UrlBase`).
3. Ative a **atualização agendada** (ex.: diária às 08:00). A cada trimestre, o merge do PR de dados atualiza os CSVs de `poc/` na `main` e a próxima atualização agendada os carrega — ninguém abre, atualiza ou salva arquivo.

O .pbix enviado por e-mail continua sendo uma fotografia: quem precisar dele offline deve exportá-lo do serviço (Baixar o arquivo .pbix) depois da atualização. Essa rotina não foi testada ponta a ponta nesta entrega (depende de uma conta do Power BI Service com workspace).

**Automação.** Os workflows `build-dashboard.yml` e `atualiza-fundamentos.yml` (em `.github/workflows/`) rodam `poc/build_poc.py` e `powerbi/gera_pbip.py` e comitam `poc/` e `powerbi/projeto/`. Cópias de referência em `poc/workflows/`. `atualiza-fundamentos.yml` antecipa o trimestre novo pelo Yahoo Finance, mas ele entra **provisório** (`fonte_dado` = agregador) e a regra R7 marca todos os seus valores com ressalva até a troca pelo release.

**Rotina trimestral (fonte primária).**

1. Coletar os releases do trimestre de cada empresa em `poc/coleta/<TICKER>.json`, na definição padronizada (ver abaixo), com URL e linha de origem por campo. Petrobras em R$.
2. Acrescentar a PTAX diária do trimestre em `poc/ptax/raw.txt` (boletim de fechamento do Banco Central).
3. `python3 poc/integra_fontes_primarias.py` (substitui os valores, converte a Petrobras e confere a dívida em US$ contra a divulgada; o script é idempotente).
4. `python3 poc/build_poc.py` e ler os alertas pendentes: cada um vira uma entrada em `poc/leituras.json` (explicação, implicação para a análise, link e trecho do release) ou uma correção de dado.
5. `python3 -m pytest tests -q`, PR, merge. O Power BI Service se atualiza sozinho (acima).

**Fontes primárias e câmbio.** Toda a série 1T25–2T26 vem dos documentos das empresas (8-K/10-Q/10-K, 6-K, releases e ITR), na mesma definição do 1T25; a coleta de cada trimestre, com URL, componentes e trechos, está em `poc/coleta/`. A Petrobras é convertida pela PTAX do Banco Central: fluxos (receita, lucro, EBITDA, FCO, capex) pela média dos dias úteis do trimestre e dívida líquida pela PTAX de fechamento do último dia útil (`poc/contexto_mercado.json`, bloco `ptax`; diário em `poc/ptax/raw.txt`). A regra R7 confere a dívida convertida contra a dívida em US$ que a companhia divulga (tolerância 0,5%).

**Coleta automática (reguladores).** `poc/coleta_sec_xbrl.py` recalcula ExxonMobil e Chevron pela API XBRL da SEC (10-Q/10-K; 4T = ano − 9 meses; junta os dois CIKs da ExxonMobil após a reorganização do 2T26) e `poc/coleta_cvm.py` recalcula a Petrobras pelos Dados Abertos da CVM (ITR/DFP consolidados, em R$). Os dois têm `--verificar`, que compara com `poc/coleta/` (tolerância 0,5%), e rodam no workflow `valida-coleta.yml` (dia 20 de cada mês e sob demanda). Conferência feita em 03/10/2026: XBRL bate com os releases nos 12 trimestres de XOM e CVX (testes com dados reais em `tests/fixtures/xbrl/`). Limites: a receita da ExxonMobil ("Sales and other operating revenue") não existe como conceito XBRL sem dimensão e continua vindo do release; o script da CVM foi testado com arquivos sintéticos no layout oficial, mas não contra os arquivos reais (o domínio da CVM estava bloqueado neste ambiente) — a primeira execução do workflow é a validação.

**Dívida sem arrendamentos e EBITDA ajustado.** `poc/decomposicao.json` guarda o passivo de arrendamento por empresa e trimestre e o EBITDA ajustado na definição de cada empresa (Petrobras: sem eventos exclusivos; Shell e TotalEnergies: Adjusted EBITDA). Dois indicadores complementares saem daí: dívida líquida sem arrendamentos/EBITDA TTM e margem EBITDA ajustada. Nas americanas (US GAAP) só o arrendamento financeiro está na dívida, e o XBRL só traz o saldo anual. Cuidado de leitura: o EBITDA sob IFRS 16 já exclui o custo do arrendamento, então tirar o arrendamento só do numerador favorece as empresas IFRS.

**Leituras de release.** Um alerta amarelo de desvio (R4) que o release explica — impairment, efeito de tempo de derivativos, capital de giro, parcelas de imposto — é fechado por uma entrada em `poc/leituras.json`. O alerta passa a "explicado pelo release", o valor não muda e a leitura informa como usá-lo (ex.: "base do 4T25 deprimida por impairment; não usar como início de tendência"). Leitura nunca fecha vermelho.

## Metodologia e fontes

- Fontes: série trimestral 1T25–2T26 dos releases e demonstrações oficiais de cada empresa (`poc/coleta/`); FY2025 de [stockanalysis.com](https://stockanalysis.com), com a dívida líquida igualada ao release do 4T25 (mesma data-base); dados de mercado do Yahoo Finance (automação diária); câmbio PTAX do Banco Central. O catálogo completo está em `poc/fontes.json`.
- **Petrobras**: demonstrações originais em R$ (gravadas por trimestre em `conversao_brl`), convertidas pela PTAX do Banco Central — média do trimestre para fluxos, fechamento para a dívida líquida. Métricas de mercado já nativas em USD (ADR na NYSE).
- **Dívida líquida padronizada** em toda a série: dívida financeira **com arrendamentos** − caixa (e aplicações de curto prazo quando a empresa as trata como caixa). BP e TotalEnergies divulgam net debt sem arrendamentos; onde a fonte trouxe a métrica oficial, o valor foi levado à base padronizada e a origem fica em `fonte_dado`.
- **Definições por empresa (série trimestral)**: EBITDA = lucro antes de impostos + juros + DD&A (incluindo impairments); Equinor = resultado operacional líquido + DD&A/impairments; BP = PBIT + DD&A + impairment; Petrobras = EBITDA da companhia (RCVM 156), não o ajustado. Capex = investimento em caixa como a empresa define (Shell: *cash capex*, inclui JVs; BP: *capital expenditure* total, inclui aquisições). Receita: Equinor usa *total revenues and other income*; TotalEnergies, *revenues from sales* (líquida de excise). BP: dívida com arrendamentos brutos (a métrica oficial da bp desconta ~US$ 1 bi de valores a receber de sócios desde o 2T25). Brent de contexto: spot Europa da EIA (FRED, DCOILBRENTEU), média dos dias do trimestre; difere do Brent datado dos releases em até 2%.
- **BP FY2025**: lucro líquido atribuível próximo de zero (US$ 55 milhões) por itens não recorrentes.
- **Correção (v1.3) — Equinor e TotalEnergies NÃO estão em caixa líquido.** As versões até a 1.2 traziam a dívida líquida negativa no FY2025 e no 1T26 por inversão da convenção "net cash (debt)" da fonte. Os controles da PoC (R4 e R8) detectaram a inversão: o FY2025 tinha o mesmo módulo do 4T25, na mesma data-base, com sinal oposto. Os releases confirmam dívida líquida positiva. Impacto: ND/EBITDA, EV e o score de solidez dessas duas empresas estavam distorcidos no dashboard.
- **Correção (v1.3) — BP**: o FY2025 (22.200) e o 1T26 (25.300) eram o net debt oficial sem arrendamentos, misturado a uma série padronizada com arrendamentos (~35.800). Ambos foram levados à base padronizada (35.815 e 38.942, este estimado).
- **Equinor FY2025**: produção anual preenchida com 2.137 kboe/d (média dos quatro trimestres de 2025), em vez do proxy do trimestre.
- **Reconciliação conhecida**: o FY2025 (stockanalysis.com) não fecha com a soma dos trimestres para EBITDA (ex.: ExxonMobil 59.530 vs. 67.864), por diferença de definição entre provedores. Comparações trimestrais devem usar a série trimestral.
- **Efetivo**: bloco `efetivo` por empresa (31/12/2024 e 31/12/2025), com a fonte e a indicação de primária ou secundária.
- **Dividend yield da Petrobras**: ~5,34% (stockanalysis.com), mas varia de 5,3% a 9,3% entre fontes — tratar como faixa.
- **Anualização** do trimestre é uma simplificação: ignora sazonalidade, paradas de manutenção e capital de giro.

⚠️ Os dados de mercado são atualizados automaticamente todo dia útil (a data do último snapshot está no rodapé do dashboard). Os **fundamentos** continuam ancorados em FY2025 e no trimestre mais recente (2T26) e só mudam quando sai um balanço novo — ou seja, múltiplos como P/E e EV/EBITDA combinam preço de hoje com lucro de ontem, que é como o mercado os calcula mesmo. Conteúdo informativo, não é recomendação de investimento.
