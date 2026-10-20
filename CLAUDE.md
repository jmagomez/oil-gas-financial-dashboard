# Dashboard Óleo & Gás — briefing do projeto

## Objetivo

Manter um dashboard comparativo de **28 indicadores** (17 primários, 11 derivados) de 7 petroleiras — ExxonMobil, Chevron, Shell, BP, Equinor, TotalEnergies, Petrobras — publicado no GitHub Pages, com dados de mercado atualizados **todo dia útil** e fundamentos revisados **a cada balanço**.

O `README.md` é o documento de referência para quem usa ou lê o dashboard: o que cada indicador significa, o que cada seção mostra, metodologia e fontes por empresa. Este arquivo é o complemento operacional, para quem vai editar o código ou os dados — leia os dois, nunca só um.

## Fontes

- **Mercado** — `yfinance` (Yahoo Finance), coletado por `update_market_data.py`. Automático, sem revisão humana.
- **Fundamentos** — `yfinance` também devolve os números, mas `update_fundamentals.py` só promove um trimestre novo depois de passar por checagens de coerência contábil (ver abaixo); a divulgação em si ainda é conferida à mão antes de rodar sem `--dry-run` em produção. É por isso que mercado roda diário sem supervisão e fundamentos não.
- **`indicadores_oleo_gas.json`** é a fonte única de verdade. `dashboard_oleo_gas.html` e `indicadores_oleo_gas.csv` são **gerados** por `build_dashboard.py` — nunca editados à mão, e nenhum indicador derivado é gravado no JSON.

## Convenções

- **Escrita cirúrgica.** O JSON é curado à mão, com objetos compactos de uma linha e zeros à direita preservados (`"pe": 10.70`, não `10.7`). Reserializar com `json.dump()` trocaria centenas de linhas de formatação a cada execução automática, e o histórico do arquivo deixaria de ser legível — foi exatamente esse bug que motivou o desenho atual (ver docstring de `update_fundamentals.reescreve_json`). As primitivas desse padrão (achar cada ticker no texto, serializar um bloco na ordem canônica, sincronizar `atualizado_em`) vivem em `escrita_cirurgica.py`, compartilhado por `update_market_data.py` e `update_fundamentals.py`. Ao tocar nessas rotinas, use as primitivas do módulo em vez de reimplementar regex local — foi assim que as duas rotinas acumularam a mesma lógica duplicada (e o mesmo formato de bug possível) antes da extração.
- **O pareamento ticker→bloco é a parte perigosa.** `posicoes_dos_tickers` decide *onde* cada bloco é gravado. Se a lista sair deslocada em uma posição, cada empresa recebe o bloco da seguinte — e isso **não quebra nada visível**: o arquivo continua JSON válido, nenhum campo some, e só os números ficam trocados entre companhias. Por isso a primitiva recorta a busca para dentro de `"empresas"` e confere a sequência encontrada no texto contra a estrutura do JSON, recusando em vez de gravar na dúvida. Não relaxe essas duas guardas: uma chave `"ticker"` acrescentada em `referencia` (um registro de exceções, um mapa de ADS) bastava para disparar o caso, e o recorte sozinho não cobre um `"ticker"` extra *dentro* de uma empresa — por isso são duas.
- **Dois regimes, duas cadências.** Mercado muda todo pregão; fundamentos mudam a cada balanço. Nunca misture as duas rotinas — `update_market_data.py` não toca em receita/EBITDA/capex/dívida/produção, e `update_fundamentals.py` não toca em cotação/P-E/dividend yield.
- **Fail-safe por campo, nunca por arquivo.** Um campo fora da faixa de plausibilidade ou com variação implausível é descartado e o valor antigo é mantido; a rotina só falha (workflow vermelho) se *nenhum* ticker responder. Dado curado não é sobrescrito em silêncio — mas veja a ressalva sobre memória em "Validação de mercado": o preço dessa garantia é que dado velho também não avança em silêncio.
- **TTM, não trimestre × 4.** Margens e múltiplos usam base de 12 meses (soma dos 4 últimos trimestres), não o trimestre mais recente anualizado — setor cíclico com capex e produção sazonais distorce qualquer anualização simples. Ver `calcular_ttm`/`consolidar_margem` em `build_dashboard.py` e a seção "Base de 12 meses" do README.
- **Commits automáticos** seguem o padrão `dados: atualiza mercado (DD/MM/AAAA)` / `dados: atualiza fundamentos`, autor `github-actions[bot]`. Esses commits usam o `GITHUB_TOKEN` padrão, então **não** disparam outros workflows `on: push` (proteção anti-recursão do GitHub) — `build-dashboard.yml` só dispara por edição humana direta no JSON/template/build script, ou por `workflow_dispatch`.
- **O corpo do commit automático é a saída da própria rotina**, capturada com `tee` e reusada no `git commit -m`. Não reimplemente o resumo dentro do YAML: já houve ali um heredoc Python que repetia `Relatorio.resumo()` sem teste nenhum, rodando depois do arquivo gravado — qualquer renomeação em `para_json()` passava verde na suíte e estourava no workflow.

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
tests/                   pytest — fórmulas derivadas, as duas rotinas de escrita, e-mail, a11y
.github/workflows/
  atualiza-mercado.yml      seg-sex 22:00 UTC — mercado + build + teste + commit + e-mail
  atualiza-fundamentos.yml  dia 5 do mês — fundamentos + build + teste + commit
  build-dashboard.yml       on push (json/template/build_dashboard.py) — rede de segurança para edição manual
  ci.yml                    lint/format informativos + pytest bloqueante, em push/PR
```

## Regras de negócio

### Validação de mercado
- Faixas de plausibilidade por campo (ex.: P/E entre 0,5 e 200).
- Limite de variação por atualização, **por campo**: `VARIACAO_MAX` em `update_market_data.py` é a fonte única (hoje 40% preço/market cap, 60% dividend yield, 70% P/E e EV/EBITDA). Não repita esses números em prosa — a documentação já divergiu do código uma vez aqui, justamente no campo que mais congela. A mensagem de rejeição cita o limite efetivo.
- **Rejeição não tem memória.** O valor antigo é mantido e a rejeição vai para o relatório e para o corpo do commit, mas nada no repositório registra *há quanto tempo* um campo deixou de avançar. Em consequência, um movimento real acima do limite congela o campo indefinidamente: toda execução seguinte compara com a mesma base velha e rejeita de novo, com o workflow verde. Antes de mexer na validação, confira no log de commits se alguma rejeição vem se repetindo — hoje três vêm (`BP ev_ebitda`, `BP dividend_yield_pct`, `PBR dividend_yield_pct`, desde 20/07/2026).
- Dividend yield: `yfinance` já devolveu esse campo tanto como fração (`0.0278`) quanto como percentual (`2.78`) — ambiguidade silenciosa de 100×. A rotina prefere calcular o yield a partir do dividendo anual e do preço (sem ambiguidade de unidade) e só usa o campo pronto como último recurso, desambiguado por magnitude.

### Validação de fundamentos
- Um trimestre só é promovido se for **mais novo** que o que já está no arquivo — mesmo trimestre devolvido pela fonte não toca nada.
- Coerência entre demonstrações (FCF = FCO + capex, EBITDA ≤ receita, margem batendo com lucro/receita) é checada **além** da faixa por campo: um número plausível no campo errado passa na faixa mas não na identidade contábil. Coerência quebrada descarta a empresa inteira naquele run — meio balanço errado é pior que nenhum.
- Divergência acima de 5% entre o dado curado e o que a fonte devolve vira aviso no relatório, não bloqueio.

### Escrita no JSON
- `update_market_data.reescreve_json` reescreve o bloco `mercado` de **todas** as empresas a cada execução (por isso precisa reproduzir byte a byte o que não mudou). `update_fundamentals.reescreve_json` só toca os tickers com trimestre novo — uma empresa sem novidade nunca passa por `serializa_bloco`. É por desenho que só o primeiro tem teste de round-trip byte a byte; o segundo não precisa dessa garantia porque simplesmente não lida com dado não tocado.
- Depois de reescrever, `update_market_data.main` confere o resultado contra o calculado: campos não-mercado intactos **e** o bloco `mercado` de cada empresa igual ao calculado para *ela*. A segunda conferência é a única que pega bloco trocado entre companhias — todas as outras passam nesse cenário. `update_fundamentals.py` não tem conferência pós-escrita equivalente; hoje depende só das guardas de `posicoes_dos_tickers`.
- Um commit de mercado mexe em ~8 linhas por empresa tocada; um commit de fundamentos (um trimestre, uma empresa) mexe em ~11 linhas. Se um diff desses ficar muito maior, é sinal de reserialização acidental do arquivo inteiro — é exatamente essa regressão que `test_formato_do_arquivo_vivo_suporta_escrita_cirurgica*` guarda, rodando contra o JSON real, não um fixture congelado.

### Notas publicadas
- As `notas` de `referencia` vão para o rodapé do dashboard, **literalmente**. Uma nota desatualizada não é documentação interna errada: é informação errada no ar, para um público que lê múltiplos. Quatro delas já tinham divergido dos dados (rótulo de trimestre, ×4 vs. TTM, esquema do histórico, marcador inexistente). Antes de escrever uma nota, pergunte se o fato que ela afirma pode mudar sozinho — se puder, não escreva o fato ali: `atualiza_datas` sincroniza a data, e **só** a data.

## Ao mexer no código

- `pytest` roda a suíte inteira (ver `pyproject.toml` — `testpaths = ["tests"]`, `addopts = "-q"`, `pythonpath = ["."]`). A raiz entra no `sys.path` pelo `pythonpath`; não acrescente `sys.path.insert` em arquivo de teste novo. Instale `requirements-dev.txt` (+ `requirements-market.txt` se for tocar nas rotinas de coleta). Testes de fundamentos usam `pytest.importorskip("pandas")` em alguns arquivos para não dar falso-verde quando a dependência falta — `tests/test_update_fundamentals_reescrita.py` é deliberadamente livre de pandas, para cobrir a reescrita mesmo sem essa dependência no ambiente.
- `ruff check .` e `ruff format --check .` no `ci.yml` são **informativos** (`continue-on-error: true`); só `pytest` é bloqueante. Mesmo assim, código novo deve nascer limpo nos dois — não acumule a dívida que já existe no restante do repositório.
- Todo defeito corrigido ganha um teste que nomeia o defeito (ver histórico de `tests/` — cada guard de regressão tem uma frase dizendo qual bug ele impede de voltar).
- Antes de commitar uma edição manual em `indicadores_oleo_gas.json`: rode `build_dashboard.py` (confere os avisos de validação impressos), depois `pytest -q`. Nunca edite `dashboard_oleo_gas.html` ou `indicadores_oleo_gas.csv` diretamente — a próxima execução automática sobrescreve.
- Mudança nas duas rotinas de escrita (`update_market_data.py`, `update_fundamentals.py`) que repita lógica de "achar ticker" / "serializar bloco" / "sincronizar data" pertence a `escrita_cirurgica.py`, não a uma cópia local.
