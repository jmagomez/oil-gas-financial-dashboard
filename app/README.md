# Dashboard Óleo & Gás — camada de apresentação (React + Vite)

App que lê o `indicadores_oleo_gas.json` publicado pelo pipeline Python deste
repositório e o apresenta de forma interativa, acessível e comparável.

> **Divisão por público.** O [`README.md` da raiz](../README.md) é para quem _lê_
> o dashboard: o que cada um dos 27 indicadores significa, metodologia e fontes
> por empresa. O [`CLAUDE.md`](../CLAUDE.md) é para quem _edita_ o pipeline.
> Este arquivo é para quem _edita o frontend_: arquitetura, stack e as decisões
> de interface. Nenhum dos três repete o outro — divergir é como eles apodrecem.

---

## Por que existe um app, se já havia um dashboard

O dashboard atual (`dashboard_oleo_gas.html`, 128 KB, gerado pelo pipeline)
funciona e continua no ar. A reescrita se justifica por **três motivos
concretos**, e é honesto dizer que _performance não é um deles_:

1. **Acessibilidade.** O HTML atual desenha os gráficos em **65 elementos
   `<canvas>`** via Chart.js. `<canvas>` é um retângulo de pixels: um leitor de
   tela não encontra ali nem rótulo, nem série, nem valor. Não há como
   remendar isso sem trocar a camada de desenho. Aqui os gráficos são SVG
   (Recharts) e cada um vem com **tabela equivalente** do mesmo dado.
2. **Interatividade de verdade.** Comparar 7 empresas × 27 indicadores × N
   trimestres exige selecionar, filtrar e cruzar. Isso é estado compartilhado
   entre componentes — exatamente o que fica insustentável em script solto
   dentro de um template de 79 KB.
3. **Testabilidade.** Regras de leitura ("este nível é alto _para esta
   empresa_") são lógica de domínio e merecem teste unitário, não inspeção
   visual.

**O custo, dito claramente:** o payload de dados tem ~21 KB. O framework
(React + Recharts + Radix) pesa mais que os dados que renderiza. Em tempo de
primeira pintura, o HTML estático ganha. Trocamos bytes por acessibilidade,
interação e manutenibilidade — uma escolha, não um upgrade gratuito.

---

## Stack, e o motivo de cada peça

| Peça       | Escolha                                                                             | Por quê                                                                                                                                                            |
| ---------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Build      | **Vite 5**                                                                          | Sem SSR na equação (o dado é um JSON estático publicado em Pages), Next.js só acrescentaria servidor que não vamos usar.                                           |
| Linguagem  | **TypeScript** `strict` + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` | O payload tem campos que podem **faltar** (produção da Equinor, por exemplo). Sem essas flags, campo ausente vira `undefined` silencioso dentro de uma conta.      |
| Estilo     | **Tailwind** + tokens CSS                                                           | Tema claro/escuro por variável CSS, uma fonte de verdade para cor.                                                                                                 |
| Primitivos | **Radix UI**                                                                        | Abas, tooltip e toggle com teclado, foco e ARIA corretos de fábrica. Reimplementar isso à mão é onde a acessibilidade de dashboard morre.                          |
| Gráficos   | **Recharts** (SVG)                                                                  | SVG é inspecionável por leitor de tela e por teste. Chart.js foi descartado **por causa do `<canvas>`** — é o defeito que motivou a reescrita.                     |
| Dados      | **TanStack Query**                                                                  | Cache, estados de carregamento e erro sem reinventar.                                                                                                              |
| Validação  | **Zod** na fronteira                                                                | O produtor é um pipeline Python que evolui em outro ritmo. Campo renomeado lá falha aqui **nomeando o campo**, em vez de virar gráfico vazio três camadas adiante. |
| Testes     | **Vitest** + Testing Library + **axe-core**                                         | a11y é requisito, então é teste, não promessa.                                                                                                                     |

Não há **Zustand nem Context de estado**: o dado é um JSON só, servido pelo
TanStack Query, e a seleção de empresas vive na URL (`?empresas=XOM,PBR`).
Acrescentar store global aqui seria estado duplicado — e `?empresas=` tem a
vantagem de ser **compartilhável**, que é o que alguém faz com uma comparação.

---

## Estrutura de diretórios

```
app/
├── public/                     favicon e estáticos copiados sem processar
├── scripts/
│   └── validate-data-contract.ts   roda no CI: valida o JSON REAL contra os schemas Zod
├── src/
│   ├── app/                    bootstrap: App, providers, ErrorBoundary por aba
│   ├── components/
│   │   ├── ui/                 primitivos SEM domínio: Card, Tabs, Skeleton, ThemeToggle,
│   │   │                       SeletorPeriodo
│   │   ├── charts/             ChartContainer (exige descrição acessível) + ChartDataTable
│   │   │                       (a tabela equivalente) + GraficoPonte/Barras/Dispersao/Radar
│   │   └── features/           painéis que conhecem o domínio: comparativo, ponte de caixa,
│   │                           eficiência, valuation, perfil
│   ├── hooks/                  acesso a dado e a tema (use-indicadores, use-theme)
│   ├── services/
│   │   ├── http-client.ts      fetch + erro tipado
│   │   ├── indicadores-api.ts  a fonte curada (só primários)
│   │   ├── dashboard-data-api.ts   o payload ENRIQUECIDO — é o que os painéis usam
│   │   └── schemas/            indicadores.schema.ts + dashboard-data.schema.ts
│   ├── lib/                    funções PURAS: formatação pt-BR, derivações de leitura
│   │                           (derivacoes.ts, ponte.ts, formatters.ts)
│   ├── types/                  o contrato em TypeScript + guard de divergência vs Zod
│   └── styles/                 globals.css com os tokens de tema
└── tests/
    ├── unit/                   funções puras de lib/
    ├── integration/            painéis renderizados contra fixture real
    ├── a11y/                   axe-core nos painéis de tabela e gráfico
    └── fixtures/               recortes do JSON REAL, nunca números inventados
```

### Propósito de cada pasta principal

- **`components/ui`** — primitivos que não sabem nada sobre petróleo. Um `Card`
  aqui serve a qualquer painel. A fronteira é dura de propósito: assim que um
  componente precisa saber o que é "FCF yield", ele não pertence a `ui`.
- **`components/charts`** — todo gráfico e, junto, a **tabela equivalente** do
  mesmo dado. Andam juntos porque a tabela não é um extra de acessibilidade: é
  também como um analista confere um valor exato sem passar o mouse ponto a
  ponto. Por isso ela é visível sob demanda, não escondida em `sr-only` —
  recurso útil para todos desaparece quando só o leitor de tela o alcança.
- **`components/features`** — painéis com a regra de leitura do domínio: quais
  indicadores entram, em que ordem, com que ressalva. É aqui que mora a resposta
  a "o que este número quer dizer".
- **`hooks`** — acesso a dado (um hook por payload, com a mesma política de
  cache) e a tema. Nenhuma regra de negócio: hook que calcula indicador esconde
  a conta de quem procura por ela em `lib`.
- **`services`** — a **fronteira**. Nada fora daqui chama `fetch`, e nada sai
  daqui sem passar por Zod. Concentrar isso é o que torna "o pipeline mudou o
  payload" um erro localizado em vez de um sintoma distante.
- **`lib`** — funções puras, testáveis sem renderizar nada. Formatação pt-BR
  (vírgula decimal, ponto de milhar) e as derivações de _leitura_ — como situar
  um indicador dentro da faixa histórica da própria empresa.
- **`types`** — o contrato como interface legível, mais um **guard em tempo de
  compilação** que falha o `tsc` se a interface e o schema Zod deixarem de
  descrever a mesma forma. Duas descrições da mesma coisa divergem em silêncio;
  esta não consegue.
- **`tests`** — separado por tipo porque o custo é diferente: `unit` roda em
  milissegundos, `a11y` levanta DOM e axe. `fixtures` guarda **recortes do JSON
  real**, para os testes afirmarem valores que existem.

**Duas pastas que a convenção pediria e que eu não criei, com justificativa:**

- **`context/`** — não há Context de estado a guardar. O dado remoto é do
  TanStack Query, o tema é um hook de 20 linhas sobre `localStorage` +
  `matchMedia`, e a seleção de empresas vive na URL. Uma pasta `context` aqui
  seria um diretório com um arquivo que não precisa existir.
- **`utils/`** — virou `lib/`, e por intenção: `utils` é o nome que convida ao
  depósito de tudo que não achou lugar. O que entra em `lib` é função pura com
  teste; o que não é isso pertence a `services` (I/O) ou a `features` (domínio).

---

## Rodando localmente

```bash
cd app
npm ci
npm run dev        # http://localhost:5173
```

Um middleware do Vite (`serveDadosDaRaiz`, em `vite.config.ts`) serve os JSON
da **raiz do repositório** em `/data/`, com lista de permissão por nome. Então
**não há cópia do dado dentro de `app/`**: a fonte continua sendo um arquivo só,
e o deploy copia os mesmos arquivos para `/app/data/`.

> A primeira versão disto usava `server.proxy` com `bypass` e estava quebrada —
> proxy encaminha para outro servidor, e aqui não há outro: o arquivo está no
> disco, um nível acima da raiz do Vite. O resultado era `index.html` no lugar
> do JSON e HTTP 500 no segundo arquivo. Nada no gate testa o dev server, então
> passou da primeira publicação. Se mexer nisso, confira com `curl` de verdade.

| Comando                 | O que faz                                    |
| ----------------------- | -------------------------------------------- |
| `npm run dev`           | servidor de desenvolvimento com HMR          |
| `npm run typecheck`     | `tsc --noEmit`                               |
| `npm run lint`          | ESLint com `--max-warnings 0`                |
| `npm run format:check`  | Prettier em modo verificação (bloqueia o CI) |
| `npm test`              | Vitest, uma vez                              |
| `npm run test:a11y`     | só a suíte de acessibilidade                 |
| `npm run validate:data` | valida os DOIS JSON reais contra os schemas  |
| `npm run build`         | typecheck + bundle de produção               |

O gate do CI roda exatamente esses, nesta ordem, e **o mais rápido falha
primeiro**.

---

## Requisitos de qualidade, e como cada um é cumprido

**Responsividade.** Grid de uma coluna no telefone, duas a partir de `lg`.
Tabelas comparativas (7 empresas × N colunas) não cabem em 390 px e **rolam na
horizontal** em vez de quebrar — com `min-width` explícito, porque tabela
financeira reflowada deixa de ser comparável.

**Tema claro/escuro.** Tokens CSS trocados por classe na raiz, com transição de
180 ms. A preferência inicial é lida em script **bloqueante** no `index.html`,
antes da primeira pintura, para não haver flash de tema errado.

> Armadilha registrada: medir contraste com `getComputedStyle` logo após trocar
> a classe de tema devolve a cor **interpolada** no meio da transição. Já me fez
> reportar uma falha de contraste que não existia. Qualquer medição espera a
> transição terminar.

**Acessibilidade.** Primitivos Radix (abas com setas/Home/End, foco gerenciado,
ARIA correto). Todo gráfico tem tabela equivalente. Nada é comunicado **só por
cor** — sinal de alta/baixa aparece no próprio número (WCAG 1.4.1). `axe-core`
roda na suíte, com os painéis de tabela cobertos explicitamente, porque é em
tabela de dados que `scope` ausente e `caption` faltando passam despercebidos.

**Performance.** Cada painel entra por `React.lazy()`, e o Recharts fica num
chunk assíncrono próprio — abrir a visão geral não baixa o código dos outros
painéis. Skeletons por card, com `aria-busy` e `aria-live`, dimensionados para
não causar salto de layout. State lifting mínimo: a seleção vive na URL, e cada
painel lê o que precisa.

---

## As cinco abas, e a ressalva de cada uma

A ordem não é arbitrária: **Comparativo → Ponte de caixa → Eficiência →
Valuation → Perfil**. Vai do agregado ao específico, e deixa o radar por último
de propósito — ele é o painel mais fácil de ler errado, e só faz sentido depois
dos números absolutos.

Em cada painel, a ressalva está em **texto visível**, não em tooltip. Num
dashboard financeiro, o aviso que impede uma conclusão errada é entregável, não
enfeite — e há teste de integração afirmando que ele está na tela, então apagar
derruba a suíte.

| Aba                | O que mostra                                                                 | A ressalva que ela carrega                                                                                               |
| ------------------ | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **Comparativo**    | Receita, EBITDA, FCF, margem, alavancagem, EV/EBITDA                         | Alavancagem indisponível quando o ROE é perto de zero, com o motivo visível; caixa líquido não é alavancagem negativa    |
| **Ponte de caixa** | Receita → EBITDA → FCO → FCF, passo a passo                                  | Capital de giro, impostos e juros aparecem **juntos** (a fonte não os abre); o resíduo é exposto, não escondido          |
| **Eficiência**     | EBITDA e receita por boe, conversão de caixa, intensidade de capex, produção | Receita/boe **não** é realização de upstream; produção por procuração é sinalizada; a Shell publica duas bases           |
| **Valuation**      | EV/EBITDA × ROE (bolha = market cap) e dividend yield × FCF yield            | Múltiplo de mercado é _snapshot_, não fechamento fiscal; o yield da Petrobras é uma **faixa** (~5% a ~9%), não um número |
| **Perfil**         | Radar de seis eixos, até 4 empresas                                          | Posição relativa, não magnitude; e o eixo Valuation pontua múltiplo **baixo** como alto                                  |

### Sobre a ponte de caixa

Cada passo é uma subtração entre campos do mesmo período — nada é estimado. Dois
pontos merecem atenção:

**O passo agregado.** Entre EBITDA e fluxo de caixa operacional há capital de
giro, impostos e juros. O payload não os abre em campos separados, então eles
aparecem num passo só, rotulado como agregado. Inventar a abertura seria afirmar
números que a fonte não tem.

**O resíduo.** `FCF − (FCO + capex)` deveria ser zero e quase sempre é. A Shell
em FY2025 tem FCO 42.863 + capex −18.948 = 23.915 contra FCF publicado de
**23.916** — um dólar, por arredondamento na fonte; os outros 13 casos fecham
exato. As barras **não** são forçadas a fechar, e o resíduo aparece com o rótulo
de arredondamento quando fica abaixo de 1% do FCF, ou destacado quando passa
disso.

### Sobre o radar, com mais cuidado

Os seis eixos vêm **já normalizados de 0 a 100 pelo pipeline** — o app não
recalcula escala, e o domínio do gráfico é fixo em `[0, 100]` para que duas
seleções diferentes de empresas não produzam escalas diferentes parecendo
comparáveis.

A normalização é min-max entre as sete: o melhor do grupo recebe 100 e o pior 0
em _todo_ eixo, com dispersão real de 2× ou de 50×. É comparação de **formato**,
não de distância.

E há uma armadilha específica: **o eixo Valuation pontua múltiplo baixo como
alto**. Com isso a Petrobras aparece com 100 em Rentabilidade, Valuation e
Retorno ao acionista, e 0 em Solidez — o radar sugere que ela é a melhor do
grupo em três de seis eixos. Não é: múltiplo baixo é o preço que o mercado cobra
por controle estatal, risco político, câmbio e um regime fiscal e de dividendos
diferente. Com sete empresas, basta uma no extremo para comprimir as outras seis.

## Indicadores: o que entra, e o que eu recomendo **não** entrar

O pipeline já calcula **19 indicadores derivados** — entre eles `fcf_yield_pct`,
`conversao_fcf_pct`, `nd_ebitda_x`, `ebitda_por_boe_usd` e `ev_por_boed_usd`.
O `CLAUDE.md` tem duas regras que valem aqui: _um derivado precisa de um
consumidor_ e _nenhum indicador é função algébrica de outro_. Então a resposta
honesta a "quais indicadores novos?" é **poucos**, e a maior parte do ganho não
está em ratios novos.

### Entra: a leitura cíclica (maior ganho, zero dado novo)

Margem EBITDA de 25% não diz nada sozinha num setor cíclico. Diz muito ao lado
de "é o topo da faixa dos últimos N trimestres **desta empresa**". Isso situa o
nível no ciclo em vez de só mostrá-lo, e sai inteiramente do histórico que já
existe. É o acréscimo de maior valor por unidade de risco.

### Entra: _gearing_ = dívida líquida ÷ (dívida líquida + patrimônio)

Complementa `nd_ebitda_x` sem ser transformação dele: `nd_ebitda_x` usa o
resultado (que **desaba justo no fundo do ciclo**, inflando a alavancagem
medida), o gearing usa o balanço e continua legível no vale.

O patrimônio **não** vem de `divida_patrimonio_pct`: conferi contra os dados e
esse campo usa dívida **total**, não líquida (XOM: ND 32.860 e D/E 16,3% dariam
patrimônio de 201.595, mas via ROE dá 268.108 — o valor real). Então o
patrimônio é derivado de `lucro_liquido ÷ roe_pct`.

> **Equinor e TotalEnergies estão em caixa líquida** (ND de −11.888 e −31.499),
> o que torna o gearing negativo. Caixa líquida **não é alavancagem negativa**:
> esses dois são exibidos como "caixa líquida", nunca como barra negativa ao
> lado dos +46% da Petrobras. Gráfico que trata −40% e +46% na mesma escala
> afirma uma comparação que não existe.

### **Não** entra: "ROCE" / EBITDA sobre capital empregado

Tentador e errado por dois motivos. Primeiro, ROCE pede **EBIT**, e o payload
não tem D&A — chamar EBITDA/capital empregado de ROCE seria rotular mal.
Segundo, e decisivo: calculei, e para a Equinor dá **128%**, não porque o
retorno seja extraordinário, mas porque capital empregado encolhe quando a
dívida líquida é negativa. Um indicador que mostra 128% para 2 das 7 empresas
não informa, engana. Fica fora até haver D&A na fonte.

### Fora do alcance dos dados atuais (não é esquecimento)

| Indicador                                     | O que falta                                |
| --------------------------------------------- | ------------------------------------------ |
| Reserve life (R/P), reserve replacement ratio | reservas provadas — não existem no payload |
| Netback, breakeven de Brent para FCF          | preço realizado e estrutura de custo       |
| Payout total (dividendos + recompras)         | recompras                                  |
| Margem por segmento (upstream × downstream)   | EBITDA por segmento                        |

E uma ressalva que vale para qualquer leitura por barril: **`receita_por_boe_usd`
não é realização de upstream** para as integradas. Exxon, Shell, BP e Total têm
refino e trading dentro da receita, então o indicador mistura negócios de
margens muito diferentes. Comparar esse número entre uma integrada e a Equinor
não é comparar a mesma coisa.

### Uma leitura que o dashboard deve carregar, não esconder

A Petrobras aparece com o maior FCF yield do grupo (**13,8%**) e a maior
alavancagem (gearing **46,0%**). Isso não é "a mais barata": é o preço de
controle estatal, risco político, câmbio e um regime fiscal e de dividendos
diferente. Um dashboard que ranqueia por FCF yield sem dizer isso produz a
conclusão errada com números certos.

---

## Publicação

O deploy roda no `.github/workflows/deploy.yml` a cada push em `main`, e publica
**as duas coisas**:

```
/                               dashboard_oleo_gas.html (pipeline) — o que já estava no ar
/indicadores_oleo_gas.{json,csv}
/app/                           este app React
/app/data/indicadores_oleo_gas.json   a fonte curada
/app/data/dashboard_data.json         o payload enriquecido — é o que o app busca
```

A convivência é deliberada: as abas migram uma a uma, e nada sai do ar antes de
ter substituto. Quando o app atingir paridade, a raiz passa a apontar para ele.

> **A origem do Pages é "GitHub Actions"** (já configurada). Isso **desliga** a
> publicação por branch: nada vai ao ar sem passar por este workflow —
> inclusive o HTML do pipeline, que o workflow copia para a raiz do artefato.
> Ao mexer no passo "Monta o site", lembre que remover essa cópia derruba o
> dashboard que está no ar.

O passo termina com `test -s` em cada arquivo esperado. É guarda-chuva contra o
erro mais caro deste workflow — publicar um artefato sem o dashboard: falhar
mantém no ar o último deploy bom, publicar vazio não tem volta. E note que o
`validate:data` do gate **não** cobriria isso: ele confere os arquivos na raiz
do repositório, não dentro do artefato.

### Concorrência, e por que ela é separada por job

`build` usa `cancel-in-progress: true`; `deploy` **nunca** cancela.

Numa sequência de pushes, só o último commit importa para o que vai ao ar —
rodar o gate inteiro em cada estado intermediário gasta tempo e enche o
histórico de vermelho que ninguém vai consertar, porque o commit já foi
superado. Já interromper a ativação do Pages no meio deixa o site servindo meio
deploy, e isso não tem volta.

Isto veio de um caso concreto: **oito runs vermelhas seguidas** (#19 a #26) ao
publicar arquivos interdependentes em commits separados — cada estado
intermediário tinha `Cannot find module`. Nenhuma derrubou o site, porque
`deploy-pages` só ativa em caso de sucesso. Com o cancelamento no build, só o
estado final é avaliado.

O que isso **não** faz: tornar verde um commit quebrado. Se o último push
estiver quebrado, ele reprova — e deve. A regra de verdade é outra, e é humana:
**arquivo que depende de arquivo vai no mesmo commit.**

---

## Limites conhecidos

- **O histórico tem 4 trimestres hoje** e cresce a cada rodada do pipeline.
  Todo painel de tendência degrada de propósito: com menos de 3 pontos, mostra
  o nível e **não** desenha linha. Série de 2 pontos não é tendência.
- `nd_ebitda_x` e `fcf_yield_pct` em base TTM só existem quando há 4 trimestres
  fechados — por isso não há série histórica deles ainda.
- A produção da Equinor pode faltar no payload; onde falta, os indicadores por
  barril aparecem como ausentes, nunca como zero.
- Os dados são anuais/trimestrais. Este dashboard **não** é ferramenta de
  acompanhamento intradiário, e nada aqui é recomendação de investimento.
