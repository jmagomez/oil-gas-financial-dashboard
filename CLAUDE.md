# Dashboard Óleo & Gás — briefing do projeto

## Objetivo

Manter um dashboard comparativo de **27 indicadores** (16 primários, 11 derivados) de 7 petroleiras — ExxonMobil, Chevron, Shell, BP, Equinor, TotalEnergies, Petrobras — publicado no GitHub Pages, com dados de mercado atualizados **todo dia útil** e fundamentos revisados **a cada balanço**.

**Divisão por público, sem sobreposição.** O `README.md` é para quem _lê_ o dashboard: o que cada indicador significa, o que cada seção mostra, metodologia e fontes por empresa. Este arquivo é para quem _edita_: convenções, regras de negócio e a mecânica das rotinas. A mecânica de implementação (quais faixas, quais limites, a ambiguidade de unidade do dividend yield, o porquê da escrita cirúrgica) existe **só aqui** — o README aponta para cá em vez de repetir. Antes os dois contavam a mesma história, e manter duas versões em sincronia é como elas divergem.

## Fontes

- **Mercado** — `yfinance` (Yahoo Finance), coletado por `update_market_data.py`. Automático, sem revisão humana.
- **Fundamentos** — `yfinance` também devolve os números, mas `update_fundamentals.py` só promove um trimestre novo depois de passar por checagens de coerência contábil (ver abaixo); a divulgação em si ainda é conferida à mão antes de rodar sem `--dry-run` em produção. É por isso que mercado roda diário sem supervisão e fundamentos não.
- **`indicadores_oleo_gas.json`** é a fonte única de verdade. `dashboard_oleo_gas.html` e `indicadores_oleo_gas.csv` são **gerados** por `build_dashboard.py` — nunca editados à mão, e nenhum indicador derivado é gravado no JSON.

## Convenções

- **Escrita cirúrgica.** O JSON é curado à mão, com objetos compactos de uma linha e zeros à direita preservados (`"pe": 10.70`, não `10.7`). Reserializar com `json.dump()` trocaria centenas de linhas de formatação a cada execução automática, e o histórico do arquivo deixaria de ser legível — foi exatamente esse bug que motivou o desenho atual (ver docstring de `update_fundamentals.reescreve_json`). As primitivas desse padrão (achar cada ticker no texto, serializar um bloco na ordem canônica, sincronizar `atualizado_em`) vivem em `escrita_cirurgica.py`, compartilhado por `update_market_data.py` e `update_fundamentals.py`. Ao tocar nessas rotinas, use as primitivas do módulo em vez de reimplementar regex local — foi assim que as duas rotinas acumularam a mesma lógica duplicada (e o mesmo formato de bug possível) antes da extração.
- **Dois regimes, duas cadências.** Mercado muda todo pregão; fundamentos mudam a cada balanço. Nunca misture as duas rotinas — `update_market_data.py` não toca em receita/EBITDA/capex/dívida/produção, e `update_fundamentals.py` não toca em cotação/P-E/dividend yield.
- **Fail-safe por campo, nunca por arquivo.** Um campo fora da faixa de plausibilidade ou com variação implausível é descartado e o valor antigo é mantido; a rotina só falha (workflow vermelho) se _nenhum_ ticker responder. Dado curado não é sobrescrito em silêncio.
- **TTM, não trimestre × 4.** Margens e múltiplos usam base de 12 meses (soma dos 4 últimos trimestres), não o trimestre mais recente anualizado — setor cíclico com capex e produção sazonais distorce qualquer anualização simples. Ver `calcular_ttm`/`consolidar_margem` em `build_dashboard.py` e a seção "Base de 12 meses" do README.
- **Um derivado precisa de um consumidor.** Sete campos derivados eram calculados a cada build e lidos por ninguém — `ebitda_anualizado` e `fcf_anualizado` (sobras da migração para TTM), três `run_rate_*` além do de EBITDA e dois `delta_*`. Campo derivado novo nasce junto com o lugar onde é exibido (template, CSV ou e-mail); se não há lugar, não há campo. Exceção explícita: os campos de **procedência** (`producao_proxy`, `producao_periodo_do_dado`, `producao_defasada`, `producao_usada_kboed`, `dias_periodo`, `janela_ttm`, `base_12m_*`) existem para dizer _com que número a conta foi feita_ e são trilha de auditoria, não indicador.
- **Procedência sem leitor é procedência que não existe.** `proveniencia.producao_kboed.trimestre_do_dado` era escrito pelo `update_fundamentals.py` desde sempre e **nenhum** lugar do dashboard o lia. Em 13/11/2026 as sete empresas carregavam produção do 2T26 — quatro delas já com fundamentos do 3T26 — e a tela exibia US$/boe com cara de preciso. A produção não sai de demonstração financeira (`CAMPOS_DERIVAVEIS` não a inclui), então o pipeline carrega a do trimestre anterior ao promover um balanço: isso é correto, desde que apareça. `derivados.producao_defasada` é quem faz aparecer. Corrigir os quatro denominadores mudou o EBITDA por barril da Shell de 109,90 para 104,82 (−4,6%) e o da TotalEnergies de 84,44 para 81,75 (−3,2%).
- **Nenhum indicador é função algébrica de outro.** `payout_fcf_pct` era exatamente `100 ÷ cobertura_dividendo_x`: duas colunas da tabela, duas do CSV e dois lugares na contagem do badge para uma informação só. Ficou a cobertura, que é a leitura padrão de crédito. Indicador novo que seja transformação monotônica de um existente não acrescenta leitura — acrescenta ruído a um público que faz a conta de cabeça.
- **O gate de publicação mora nos composite actions.** `build → pytest → commit` estava escrito três vezes e já havia divergido: um workflow rodava Python 3.11 e os outros dois 3.12 para o mesmo código, e só um fazia `git pull --rebase` antes do push. Agora versão, ordem dos passos e tratamento de corrida vivem em `.github/actions/{prepara-ambiente,publica-artefatos}`. Workflow novo que escreva nos artefatos gerados usa os dois; não copie os steps.
- **Commits automáticos** seguem o padrão `dados: atualiza mercado (DD/MM/AAAA)` / `dados: atualiza fundamentos`, autor `github-actions[bot]`. Esses commits usam o `GITHUB_TOKEN` padrão, então **não** disparam outros workflows `on: push` (proteção anti-recursão do GitHub) — `build-dashboard.yml` só dispara por edição humana direta no JSON/template/build script, ou por `workflow_dispatch`.

## Estrutura

```
build_dashboard.py       deriva indicadores, valida, gera HTML + CSV (único ponto que calcula derivados)
update_market_data.py    rotina diária: mercado (cotação, market cap, P/E, dividend yield, EV/EBITDA)
update_fundamentals.py   rotina mensal: fundamentos, promove trimestre novo, checa coerência contábil
escrita_cirurgica.py     primitivas de escrita compartilhadas pelas duas rotinas acima
build_email.py           corpo do e-mail diário, reaproveita build_dashboard.enriquecer()/validate()
dashboard_template.html  esqueleto HTML/CSS/JS com o placeholder __DATA_JSON__
assets_a11y.{css,js}     camada de acessibilidade, embutida no HTML pelo build
indicadores_oleo_gas.json   fonte única de verdade — único arquivo de dados editado à mão
dashboard_oleo_gas.html  )
indicadores_oleo_gas.csv )  GERADOS — nunca editar à mão, só via build_dashboard.py
dashboard_data.json      )  (o último é o payload enriquecido que o app consome)
tests/                   pytest — fórmulas derivadas, as duas rotinas de escrita, e-mail, a11y,
                         e o contrato entre o template e o payload
.github/actions/
  prepara-ambiente/        Python 3.12 + dependências (uma versão só, para os quatro workflows)
  publica-artefatos/       gate: build -> pytest -> commit dos gerados, com rebase antes do push
app/                     camada de apresentação em React + Vite (ver app/README.md)
.github/workflows/
  atualiza-mercado.yml      seg-sex 22:00 UTC — mercado, publica pelo gate, e-mail
  atualiza-fundamentos.yml  dia 5 do mês — fundamentos, publica pelo gate
  build-dashboard.yml       on push (json/template/build/assets) — rede de segurança para edição manual
  ci.yml                    ruff check bloqueante + pytest, em PR e nos pushes que build-dashboard não cobre
  deploy.yml                on push main — gate do app + publica Pages (raiz = HTML atual, /app = React)
```

Os `paths` de `build-dashboard.yml` e os `paths-ignore` de `ci.yml` são complementares de
propósito: tudo que regenera artefato passa pelo primeiro (que é quem comita, logo é quem
precisa ser o gate), e o `ci.yml` cobre o resto. Antes os dois disparavam no mesmo push e a
suíte inteira rodava duas vezes em paralelo. Ao mexer em um, mexa no outro.

## Regras de negócio

### Validação de mercado

- Faixas de plausibilidade por campo (ex.: P/E entre 0,5 e 200).
- Limite de variação por atualização (40% preço/market cap, 70% múltiplos) — um desdobramento de ações ou troca de símbolo gera um valor válido isoladamente mas que pula de patamar; fica registrado como rejeição, não aplicado.
- Dividend yield: `yfinance` já devolveu esse campo tanto como fração (`0.0278`) quanto como percentual (`2.78`) — ambiguidade silenciosa de 100×. A rotina **prefere o `trailingAnnualDividendYield`**, que é sempre fração e é calculado pela própria fonte sobre o preço que ela publica; depois o cálculo `dividendo ÷ preço`; e só então o campo ambíguo, desambiguado por magnitude.
- **Por que o cálculo explícito não vem primeiro (armadilha de ADR).** Ele vinha, com o argumento de que taxa e preço não têm ambiguidade de escala. O argumento estava certo e incompleto: o cálculo troca uma ambiguidade por outra. Na BP, o `trailingAnnualDividendRate` veio `0.34`, que é o dividendo por ação **ordinária**, enquanto o preço é por **ADS** — e 1 ADS da BP equivale a 6 ordinárias. O resultado foi 0,76% em vez de ~4,7%: erro de exatamente 6×. O que torna isso instrutivo é que **0,76% está dentro de qualquer faixa de plausibilidade razoável** — não existe piso absoluto que separe "dividendo pequeno" de "unidade errada", porque empresa que não paga dividendo tem yield zero de verdade. A correção não é uma faixa, é a ordem das fontes. Limite que permanece: quando só existe a taxa, não há com o que cruzar e o descasamento passa — a defesa aí é o limite de variação, que foi o que barrou a BP em produção. Num ticker novo, sem valor anterior, o buraco existe e está afirmado em teste.
- **EV/EBITDA é derivado, não lido da fonte.** O `enterpriseToEbitda` do Yahoo usa outro numerador e outro denominador que os nossos, e as duas definições conviviam sob o **mesmo rótulo** "EV / EBITDA" na tela. Na carga de 08/11/2026 a divergência ia de +6% (XOM, CVX) a −52% (EQNR) e +100% (PBR, cujo 1,78× é incompatível com EV de US$ 180 bi sobre EBITDA de US$ 50 bi). O campo saiu do bloco `mercado` e virou `derivados.ev_ebitda_x`, na mesma base de 12 meses registrada em `base_12m_ebitda` — a mesma do `nd_ebitda_x`, para que alavancagem e valuation nunca usem EBITDAs diferentes sem avisar. `tests/test_contrato_template.py` guarda o arquivo vivo contra a volta silenciosa do campo, porque `reescreve_json` preserva chaves desconhecidas de propósito.

### Validação de fundamentos

- Um trimestre só é promovido se for **mais novo** que o que já está no arquivo — mesmo trimestre devolvido pela fonte não toca nada.
- Coerência entre demonstrações (FCF = FCO + capex, EBITDA ≤ receita, margem batendo com lucro/receita) é checada **além** da faixa por campo: um número plausível no campo errado passa na faixa mas não na identidade contábil. Coerência quebrada descarta a empresa inteira naquele run — meio balanço errado é pior que nenhum.
- **Moeda é checada antes de tudo, e rejeita a empresa inteira.** O arquivo declara "USD (milhões)" e a Petrobras publica em BRL — o lucro do 3T26 saiu como R$ 39,8 bilhões. O perigo é que **nenhuma** das cinco checagens de coerência pega isso: EBITDA ≤ receita, lucro ≤ receita, FCF = FCO + capex, margem = lucro/receita e capex < 0 são todas invariantes a escala, e um balanço inteiro em BRL passa nas cinco. As faixas também não resolviam, por dois motivos: em BRL a receita (~R$ 178 bi), o lucro e o EBITDA cabem nelas, e — pior — campo fora de faixa é **anulado**, não descarta a empresa, então só a dívida líquida estouraria e o trimestre entraria como USD com a dívida nula. `valida_moeda` lê o `financialCurrency` (a moeda das **demonstrações**, diferente de `currency`, que é a da **cotação**) e descarta a empresa inteira, como na incoerência.
- **`valida_escala` é a segunda linha, para quando o metadado some.** Uma guarda que depende de metadado para de guardar em silêncio se a fonte parar de informá-lo — o modo de falha mais perigoso, porque não aparece. A escala não depende de metadado nenhum: compara a receita do trimestre novo com a do curado e rejeita saltos acima de 2,5×. A calibragem saiu da própria série: a maior variação trimestral real é +43% (Petrobras, 1T26→2T26), e a conversão BRL→USD é ~5,3×. Ela também pega troca de unidade e consolidação de aquisição grande — casos em que a rejeição também é o certo, porque pedem curadoria, não promoção automática.
- **O caso que a escala não pega.** O BRL se denuncia pelo tamanho; o EUR não. Uma demonstração em euros erra por ~8%: pequeno demais para qualquer checagem de magnitude, grande o bastante para corromper toda comparação. É por isso que as duas guardas existem, e é esse o cenário de `test_moeda_errada_por_margem_PEQUENA_ainda_assim_descarta` — sem ele, remover o `continue` da guarda de moeda deixava a suíte verde, porque a rejeição por escala do caso BRL mascarava a falta.
- Divergência acima de 5% entre o dado curado e o que a fonte devolve vira aviso no relatório, não bloqueio.

### Escrita no JSON

- `update_market_data.reescreve_json` reescreve o bloco `mercado` de **todas** as empresas a cada execução (por isso precisa reproduzir byte a byte o que não mudou). `update_fundamentals.reescreve_json` só toca os tickers com trimestre novo — uma empresa sem novidade nunca passa por `serializa_bloco`. É por desenho que só o primeiro tem teste de round-trip byte a byte; o segundo não precisa dessa garantia porque simplesmente não lida com dado não tocado.
- Um commit de mercado mexe em ~8 linhas por empresa tocada; um commit de fundamentos (um trimestre, uma empresa) mexe em ~11 linhas. Se um diff desses ficar muito maior, é sinal de reserialização acidental do arquivo inteiro — é exatamente essa regressão que `test_formato_do_arquivo_vivo_suporta_escrita_cirurgica*` guarda, rodando contra o JSON real, não um fixture congelado.

## Frontend (`app/`)

O dashboard tem **duas camadas de apresentação ao mesmo tempo**, de propósito: o
`dashboard_oleo_gas.html` gerado pelo pipeline, que continua no ar, e o app
React em `app/`, que migra as análises uma a uma. Nada sai do ar antes de ter
substituto. Quando o app atingir paridade, a raiz do Pages passa a apontar para
ele e o template sai de cena.

A arquitetura, o stack e as decisões de interface estão em `app/README.md` — que
é o terceiro público desta divisão: quem edita o frontend. Aqui ficam só as
regras que **cruzam a fronteira** entre pipeline e app.

- **Dois arquivos, uma fonte.** `indicadores_oleo_gas.json` é a fonte curada e
  tem **só campos primários**. O app consome o `dashboard_data.json`, que é
  **gerado** por `build_dashboard.py` e carrega os 18 derivados, os eixos do
  radar (`perfil`) e o TTM. O fonte continua sendo o único arquivo editado à
  mão; o enriquecido é artefato, como o HTML e o CSV.

  A alternativa era reimplementar as fórmulas em TypeScript, e duas
  implementações da mesma conta divergem — remover essa duplicação foi o
  trabalho desta semana. `build_dados()` publica o **mesmo dicionário** que
  `build_html()` já injetava no lugar de `__DATA_JSON__`, e há teste
  comparando os dois: se divergirem, o dashboard antigo e o app mostram
  números diferentes para o mesmo indicador.

  **Artefato novo precisa dos três elos.** O gerador (`build_dados` chamado em
  `main`), o `git add` do composite action e a cópia no `deploy.yml`. Eu
  publiquei o `dashboard_data.json` com só um deles e o repositório ficou com
  um artefato que nenhuma rotina regenerava — envelheceria em silêncio
  enquanto HTML e CSV seguiam frescos. `test_main_gera_os_TRES_artefatos`
  existe por causa disso.

- **O app não tem cópia do dado versionada.** Em dev um middleware do Vite
  (`serveDadosDaRaiz`) serve os JSON da raiz em `/data/`, com lista de
  permissão por nome; no deploy o workflow copia os mesmos arquivos para
  `/app/data/`. Nunca versione um segundo JSON dentro de `app/`.

  Antes era `server.proxy` com `bypass`, e estava **quebrado**: proxy
  encaminha para outro servidor, e aqui não há outro — o arquivo está no
  disco. O resultado era `index.html` no lugar do JSON (1.402 bytes) e HTTP
  500 no segundo arquivo. Passou da primeira publicação porque nada testa o
  dev server; se mexer nisso, teste com `curl` de verdade.

- **O app não calcula indicador de negócio.** `build_dashboard.py` segue sendo o
  único ponto que deriva indicador — a regra "um derivado precisa de um
  consumidor" perde o sentido se o consumidor recalcular por conta própria, e
  duas implementações da mesma fórmula divergem. O que o app deriva é
  **leitura**: situar um valor na faixa histórica da própria empresa, escolher
  rótulo, decidir se há pontos suficientes para desenhar linha, e montar a
  ponte de caixa (que é subtração entre campos do mesmo período, não fórmula
  nova).

  A **ponte expõe o resíduo** em vez de fechar a conta na força: a Shell em
  FY2025 tem FCO 42.863 + capex −18.948 = 23.915 contra FCF publicado de
  23.916. Um dólar de arredondamento na fonte, e os outros 13 casos fecham
  exato. Ajustar as barras esconderia a diferença.

- **Cinco abas, e a ordem importa.** Comparativo → Ponte de caixa →
  Eficiência → Valuation → Perfil. O radar vem por último de propósito: é o
  painel mais sujeito a leitura errada, porque a normalização é min-max entre
  as sete e o eixo Valuation pontua múltiplo **baixo** como alto — a Petrobras
  sai com 100 em Rentabilidade, Valuation e Retorno ao acionista, e 0 em
  Solidez. Abrir o dashboard no radar convidaria à conclusão de que ela é a
  melhor empresa do grupo. Painel novo que ranqueia entra depois dos números
  absolutos, não antes.
- **Campo novo no payload = schema Zod antes de tela.** A fronteira de dados do
  app valida com Zod e falha nomeando o campo. Renomear campo no pipeline sem
  mexer no schema derruba o `validate:data` do deploy — isso é o desenho
  funcionando, não um estorvo. Os dois mudam no mesmo commit.
- **Ausência não é zero, do mesmo jeito que no pipeline.** A produção da Equinor
  pode faltar; onde falta, indicador por barril aparece ausente. O fail-safe por
  campo do lado Python não serve para nada se a tela preencher o buraco com 0.
- **Gráficos em SVG, não `<canvas>`.** O template atual desenha 65 `<canvas>`
  via Chart.js, e `<canvas>` é opaco para leitor de tela — foi o motivo
  principal da reescrita. Gráfico novo no app usa Recharts e vem com tabela
  equivalente; introduzir `<canvas>` reintroduz o defeito que motivou tudo isto.
- **Dois gates, não um.** `ci.yml` cobre o Python (ruff bloqueante + pytest);
  `deploy.yml` cobre o app (typecheck, lint, format:check, testes, build,
  validate:data) e só publica se tudo passar. Nenhum dos dois é informativo.
- **Arquivo que depende de arquivo vai no MESMO commit.** Publiquei o Passo 3
  em oito commits e colhi **oito runs vermelhas seguidas** (#19 a #26): cada
  estado intermediário tinha `Cannot find module`, porque o importador entrou
  antes do importado. Nenhuma derrubou o site — `deploy-pages` só ativa em
  caso de sucesso, então o deploy anterior continuou servindo — mas eram oito
  vermelhos evitáveis.

  O `deploy.yml` passou a separar a concorrência **por job**: o `build` usa
  `cancel-in-progress: true`, porque numa sequência de pushes só o último
  commit importa para o que vai ao ar; o `deploy` nunca cancela, porque
  interromper a ativação do Pages deixa o site servindo meio deploy. Isso
  reduz o ruído, mas **não torna verde um commit quebrado**: se o último push
  estiver quebrado, ele reprova — e deve.

- **A publicação por branch está desligada.** O Pages serve da origem "GitHub
  Actions", então **nada vai ao ar sem passar pelo `deploy.yml`** — inclusive o
  HTML do pipeline, que o workflow copia para a raiz do artefato. Ao mexer no
  passo "Monta o site", lembre que remover essa cópia derruba o dashboard atual.

## Ao mexer no código

- `pytest` roda a suíte inteira (ver `pyproject.toml` — `testpaths = ["tests"]`, já com `-q`, e `pythonpath = ["."]`, que dispensa `sys.path.insert` em cada arquivo de teste). Cinco arquivos ainda carregam a linha por inércia; ela é inofensiva e sai quando o arquivo for tocado por outro motivo — reescrever um arquivo de teste inteiro só para apagá-la é risco de transcrição sem retorno, sobretudo em `test_update_fundamentals.py`, que guarda números conferidos balanço por balanço. Instale `requirements-dev.txt` (+ `requirements-market.txt` se for tocar nas rotinas de coleta). Testes de fundamentos usam `pytest.importorskip("pandas")` em alguns arquivos para não dar falso-verde quando a dependência falta — `tests/test_update_fundamentals_reescrita.py` é deliberadamente livre de pandas, para cobrir a reescrita mesmo sem essa dependência no ambiente.
- `ruff check .` é **bloqueante** no `ci.yml`, e está em zero. Um gate que vive vermelho é um gate que todo mundo aprende a ignorar — foi por isso que ele deixou de ser informativo. Os seis avisos que restavam nas três rotinas de coleta estão em `[tool.ruff.lint.per-file-ignores]`, nomeados arquivo por arquivo e regra por regra: dívida **localizada e fechável**, não um `ignore` global que esconderia a mesma classe de problema em código novo. Ao mexer num desses três arquivos, limpe a regra e apague a linha do `pyproject.toml`. `ruff format --check .` segue informativo: adotar o formatter reescreveria 11 arquivos cuja formatação compacta é deliberada (ver a linha do CSV em `build_dashboard.py`), e isso é uma decisão em aberto, não dívida a pagar num PR de conteúdo. `UP017` está em `ignore` com motivo: `datetime.UTC` exige 3.11+ e travaria a suíte em ambientes 3.10 por uma troca cosmética.
- Todo defeito corrigido ganha um teste que nomeia o defeito (ver histórico de `tests/` — cada guard de regressão tem uma frase dizendo qual bug ele impede de voltar).
- **O contrato template↔payload tem teste próprio.** `tests/test_contrato_template.py` resolve cada getter de `METRICAS` contra o payload real. Existe porque um campo foi removido de `build_dashboard.py` e a entrada ficou no template apontando para `p.derivados.<campo>` inexistente: a suíte passou com 193 testes verdes e o dashboard publicado exibiu uma coluna de travessões para as sete empresas. Os testes de build conferiam o payload, os de a11y conferiam a injeção, e o contrato entre os dois não era de ninguém. Indicador novo ou removido mexe em **dois** arquivos; este teste é quem cobra o segundo.
- **Um arquivo de teste por assunto, não por episódio.** `tests/test_ajustes_auditoria.py` era nomeado pelo evento que o criou e acabou cobrindo `build_dashboard`, `update_fundamentals` e `update_market` ao mesmo tempo, com seis testes que duplicavam cobertura existente (`dias_do_trimestre` em dois arquivos, o fallback de produção em três). Teste novo vai para o arquivo do módulo que ele testa.
- Antes de commitar uma edição manual em `indicadores_oleo_gas.json`: rode `build_dashboard.py` (confere os avisos de validação impressos), depois `pytest -q`. Nunca edite `dashboard_oleo_gas.html` ou `indicadores_oleo_gas.csv` diretamente — a próxima execução automática sobrescreve.
- Mudança nas duas rotinas de escrita (`update_market_data.py`, `update_fundamentals.py`) que repita lógica de "achar ticker" / "serializar bloco" / "sincronizar data" pertence a `escrita_cirurgica.py`, não a uma cópia local.
