# Dashboard Óleo & Gás — briefing do projeto

## Objetivo

Manter um dashboard comparativo de **27 indicadores** (17 primários, 10 derivados) de 7 petroleiras — ExxonMobil, Chevron, Shell, BP, Equinor, TotalEnergies, Petrobras — publicado no GitHub Pages, com dados de mercado atualizados **todo dia útil** e fundamentos revisados **a cada balanço**.

**Divisão por público, sem sobreposição.** O `README.md` é para quem *lê* o dashboard: o que cada indicador significa, o que cada seção mostra, metodologia e fontes por empresa. Este arquivo é para quem *edita*: convenções, regras de negócio e a mecânica das rotinas. A mecânica de implementação (quais faixas, quais limites, a ambiguidade de unidade do dividend yield, o porquê da escrita cirúrgica) existe **só aqui** — o README aponta para cá em vez de repetir. Antes os dois contavam a mesma história, e manter duas versões em sincronia é como elas divergem.

## Fontes

- **Mercado** — `yfinance` (Yahoo Finance), coletado por `update_market_data.py`. Automático, sem revisão humana.
- **Fundamentos** — `yfinance` também devolve os números, mas `update_fundamentals.py` só promove um trimestre novo depois de passar por checagens de coerência contábil (ver abaixo); a divulgação em si ainda é conferida à mão antes de rodar sem `--dry-run` em produção. É por isso que mercado roda diário sem supervisão e fundamentos não.
- **`indicadores_oleo_gas.json`** é a fonte única de verdade. `dashboard_oleo_gas.html` e `indicadores_oleo_gas.csv` são **gerados** por `build_dashboard.py` — nunca editados à mão, e nenhum indicador derivado é gravado no JSON.

## Convenções

- **Escrita cirúrgica.** O JSON é curado à mão, com objetos compactos de uma linha e zeros à direita preservados (`"pe": 10.70`, não `10.7`). Reserializar com `json.dump()` trocaria centenas de linhas de formatação a cada execução automática, e o histórico do arquivo deixaria de ser legível — foi exatamente esse bug que motivou o desenho atual (ver docstring de `update_fundamentals.reescreve_json`). As primitivas desse padrão (achar cada ticker no texto, serializar um bloco na ordem canônica, sincronizar `atualizado_em`) vivem em `escrita_cirurgica.py`, compartilhado por `update_market_data.py` e `update_fundamentals.py`. Ao tocar nessas rotinas, use as primitivas do módulo em vez de reimplementar regex local — foi assim que as duas rotinas acumularam a mesma lógica duplicada (e o mesmo formato de bug possível) antes da extração.
- **Dois regimes, duas cadências.** Mercado muda todo pregão; fundamentos mudam a cada balanço. Nunca misture as duas rotinas — `update_market_data.py` não toca em receita/EBITDA/capex/dívida/produção, e `update_fundamentals.py` não toca em cotação/P-E/dividend yield.
- **Fail-safe por campo, nunca por arquivo.** Um campo fora da faixa de plausibilidade ou com variação implausível é descartado e o valor antigo é mantido; a rotina só falha (workflow vermelho) se *nenhum* ticker responder. Dado curado não é sobrescrito em silêncio.
- **TTM, não trimestre × 4.** Margens e múltiplos usam base de 12 meses (soma dos 4 últimos trimestres), não o trimestre mais recente anualizado — setor cíclico com capex e produção sazonais distorce qualquer anualização simples. Ver `calcular_ttm`/`consolidar_margem` em `build_dashboard.py` e a seção "Base de 12 meses" do README.
- **Um derivado precisa de um consumidor.** Sete campos derivados eram calculados a cada build e lidos por ninguém — `ebitda_anualizado` e `fcf_anualizado` (sobras da migração para TTM), três `run_rate_*` além do de EBITDA e dois `delta_*`. Campo derivado novo nasce junto com o lugar onde é exibido (template, CSV ou e-mail); se não há lugar, não há campo. Exceção explícita: os campos de **procedência** (`producao_proxy`, `producao_usada_kboed`, `dias_periodo`, `janela_ttm`, `base_12m_*`) existem para dizer *com que número a conta foi feita* e são trilha de auditoria, não indicador.
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
dashboard_oleo_gas.html  )  GERADOS — nunca editar à mão, só via build_dashboard.py
indicadores_oleo_gas.csv )
tests/                   pytest — fórmulas derivadas, as duas rotinas de escrita, e-mail, a11y,
                         e o contrato entre o template e o payload
.github/actions/
  prepara-ambiente/        Python 3.12 + dependências (uma versão só, para os quatro workflows)
  publica-artefatos/       gate: build -> pytest -> commit dos gerados, com rebase antes do push
.github/workflows/
  atualiza-mercado.yml      seg-sex 22:00 UTC — mercado, publica pelo gate, e-mail
  atualiza-fundamentos.yml  dia 5 do mês — fundamentos, publica pelo gate
  build-dashboard.yml       on push (json/template/build/assets) — rede de segurança para edição manual
  ci.yml                    ruff check bloqueante + pytest, em PR e nos pushes que build-dashboard não cobre
```

Os `paths` de `build-dashboard.yml` e os `paths-ignore` de `ci.yml` são complementares de
propósito: tudo que regenera artefato passa pelo primeiro (que é quem comita, logo é quem
precisa ser o gate), e o `ci.yml` cobre o resto. Antes os dois disparavam no mesmo push e a
suíte inteira rodava duas vezes em paralelo. Ao mexer em um, mexa no outro.

## Regras de negócio

### Validação de mercado
- Faixas de plausibilidade por campo (ex.: P/E entre 0,5 e 200).
- Limite de variação por atualização (40% preço/market cap, 70% múltiplos) — um desdobramento de ações ou troca de símbolo gera um valor válido isoladamente mas que pula de patamar; fica registrado como rejeição, não aplicado.
- Dividend yield: `yfinance` já devolveu esse campo tanto como fração (`0.0278`) quanto como percentual (`2.78`) — ambiguidade silenciosa de 100×. A rotina prefere calcular o yield a partir do dividendo anual e do preço (sem ambiguidade de unidade) e só usa o campo pronto como último recurso, desambiguado por magnitude.

### Validação de fundamentos
- Um trimestre só é promovido se for **mais novo** que o que já está no arquivo — mesmo trimestre devolvido pela fonte não toca nada.
- Coerência entre demonstrações (FCF = FCO + capex, EBITDA ≤ receita, margem batendo com lucro/receita) é checada **além** da faixa por campo: um número plausível no campo errado passa na faixa mas não na identidade contábil. Coerência quebrada descarta a empresa inteira naquele run — meio balanço errado é pior que nenhum.
- Divergência acima de 5% entre o dado curado e o que a fonte devolve vira aviso no relatório, não bloqueio.

### Escrita no JSON
- `update_market_data.reescreve_json` reescreve o bloco `mercado` de **todas** as empresas a cada execução (por isso precisa reproduzir byte a byte o que não mudou). `update_fundamentals.reescreve_json` só toca os tickers com trimestre novo — uma empresa sem novidade nunca passa por `serializa_bloco`. É por desenho que só o primeiro tem teste de round-trip byte a byte; o segundo não precisa dessa garantia porque simplesmente não lida com dado não tocado.
- Um commit de mercado mexe em ~8 linhas por empresa tocada; um commit de fundamentos (um trimestre, uma empresa) mexe em ~11 linhas. Se um diff desses ficar muito maior, é sinal de reserialização acidental do arquivo inteiro — é exatamente essa regressão que `test_formato_do_arquivo_vivo_suporta_escrita_cirurgica*` guarda, rodando contra o JSON real, não um fixture congelado.

## Ao mexer no código

- `pytest` roda a suíte inteira (ver `pyproject.toml` — `testpaths = ["tests"]`, já com `-q`, e `pythonpath = ["."]`, que dispensa `sys.path.insert` em cada arquivo de teste). Cinco arquivos ainda carregam a linha por inércia; ela é inofensiva e sai quando o arquivo for tocado por outro motivo — reescrever um arquivo de teste inteiro só para apagá-la é risco de transcrição sem retorno, sobretudo em `test_update_fundamentals.py`, que guarda números conferidos balanço por balanço. Instale `requirements-dev.txt` (+ `requirements-market.txt` se for tocar nas rotinas de coleta). Testes de fundamentos usam `pytest.importorskip("pandas")` em alguns arquivos para não dar falso-verde quando a dependência falta — `tests/test_update_fundamentals_reescrita.py` é deliberadamente livre de pandas, para cobrir a reescrita mesmo sem essa dependência no ambiente.
- `ruff check .` é **bloqueante** no `ci.yml`, e está em zero. Um gate que vive vermelho é um gate que todo mundo aprende a ignorar — foi por isso que ele deixou de ser informativo. Os seis avisos que restavam nas três rotinas de coleta estão em `[tool.ruff.lint.per-file-ignores]`, nomeados arquivo por arquivo e regra por regra: dívida **localizada e fechável**, não um `ignore` global que esconderia a mesma classe de problema em código novo. Ao mexer num desses três arquivos, limpe a regra e apague a linha do `pyproject.toml`. `ruff format --check .` segue informativo: adotar o formatter reescreveria 11 arquivos cuja formatação compacta é deliberada (ver a linha do CSV em `build_dashboard.py`), e isso é uma decisão em aberto, não dívida a pagar num PR de conteúdo. `UP017` está em `ignore` com motivo: `datetime.UTC` exige 3.11+ e travaria a suíte em ambientes 3.10 por uma troca cosmética.
- Todo defeito corrigido ganha um teste que nomeia o defeito (ver histórico de `tests/` — cada guard de regressão tem uma frase dizendo qual bug ele impede de voltar).
- **O contrato template↔payload tem teste próprio.** `tests/test_contrato_template.py` resolve cada getter de `METRICAS` contra o payload real. Existe porque um campo foi removido de `build_dashboard.py` e a entrada ficou no template apontando para `p.derivados.<campo>` inexistente: a suíte passou com 193 testes verdes e o dashboard publicado exibiu uma coluna de travessões para as sete empresas. Os testes de build conferiam o payload, os de a11y conferiam a injeção, e o contrato entre os dois não era de ninguém. Indicador novo ou removido mexe em **dois** arquivos; este teste é quem cobra o segundo.
- **Um arquivo de teste por assunto, não por episódio.** `tests/test_ajustes_auditoria.py` era nomeado pelo evento que o criou e acabou cobrindo `build_dashboard`, `update_fundamentals` e `update_market` ao mesmo tempo, com seis testes que duplicavam cobertura existente (`dias_do_trimestre` em dois arquivos, o fallback de produção em três). Teste novo vai para o arquivo do módulo que ele testa.
- Antes de commitar uma edição manual em `indicadores_oleo_gas.json`: rode `build_dashboard.py` (confere os avisos de validação impressos), depois `pytest -q`. Nunca edite `dashboard_oleo_gas.html` ou `indicadores_oleo_gas.csv` diretamente — a próxima execução automática sobrescreve.
- Mudança nas duas rotinas de escrita (`update_market_data.py`, `update_fundamentals.py`) que repita lógica de "achar ticker" / "serializar bloco" / "sincronizar data" pertence a `escrita_cirurgica.py`, não a uma cópia local.
