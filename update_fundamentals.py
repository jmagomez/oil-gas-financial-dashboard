#!/usr/bin/env python3
"""Atualiza os FUNDAMENTOS trimestrais do indicadores_oleo_gas.json.

Irmao de update_market_data.py, para o outro regime de dado:

    update_market_data.py  -> preco, market cap, P/E, yield   (muda todo pregao)
    update_fundamentals.py -> receita, EBITDA, caixa, divida  (muda a cada balanco)

O que faz quando uma empresa divulga um trimestre novo:

    1. move o q_recente atual para o fim de `historico` (rotulo "2026-Q1");
    2. preenche q_recente com o trimestre novo;
    3. registra em `proveniencia` de onde veio cada campo e quando.

Principios
----------
1. So age em trimestre NOVO. Se a fonte devolve o mesmo trimestre que ja esta
   no arquivo, nada e tocado -- nem para "corrigir". Dado curado nao e
   sobrescrito em silencio; divergencia vira aviso no relatorio.
2. Coerencia antes de gravar. Nao basta cada campo ser plausivel sozinho: as
   demonstracoes tem de fechar entre si (FCF = FCO + capex, EBITDA <= receita,
   margem batendo com lucro/receita). Um numero certo no lugar errado passa em
   qualquer validacao de faixa, mas nao passa numa de coerencia.
3. Producao nao vem de demonstracao financeira. E metrica operacional, sai em
   release. O script preserva o valor anterior e MARCA como carregado, para o
   dashboard nao fingir que e dado do trimestre novo.
4. Rede isolada em `busca_fundamentos`. Todo o resto e funcao pura, testada
   offline contra numeros conferidos a mao (ver tests/test_update_fundamentals.py).

Uso:
    python3 update_fundamentals.py --dry-run
    python3 update_fundamentals.py --relatorio r.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent
JSON_DADOS = RAIZ / "indicadores_oleo_gas.json"

# Campos do bloco trimestral, na ordem em que aparecem no JSON.
CAMPOS_TRIMESTRE = [
    "trimestre",
    "receita",
    "lucro_liquido",
    "ebitda",
    "margem_liquida_pct",
    "fluxo_caixa_operacional",
    "fcf",
    "capex",
    "divida_liquida",
    "divida_patrimonio_pct",
    "roe_pct",
    "roa_pct",
    "producao_kboed",
]

# Campos que o script sabe derivar das demonstracoes. Os de fora desta lista
# (hoje so producao_kboed) sao preservados do trimestre anterior e marcados.
CAMPOS_DERIVAVEIS = [
    "receita",
    "lucro_liquido",
    "ebitda",
    "margem_liquida_pct",
    "fluxo_caixa_operacional",
    "fcf",
    "capex",
    "divida_liquida",
    "divida_patrimonio_pct",
    "roe_pct",
    "roa_pct",
]

# Rotulos alternativos do yfinance. A biblioteca renomeia linhas entre versoes
# e nem toda empresa publica todas; por isso lista de sinonimos, nao chave fixa.
LINHAS = {
    "receita": ["Total Revenue", "Operating Revenue"],
    "lucro_liquido": [
        "Net Income",
        "Net Income Common Stockholders",
        "Net Income Continuous Operations",
    ],
    "ebitda": ["EBITDA", "Normalized EBITDA"],
    "ebit": ["EBIT", "Operating Income"],
    "depreciacao": ["Reconciled Depreciation", "Depreciation And Amortization"],
    "fco": ["Operating Cash Flow", "Total Cash From Operating Activities"],
    "capex": ["Capital Expenditure", "Capital Expenditures"],
    "fcf": ["Free Cash Flow"],
    "divida_total": ["Total Debt"],
    "caixa": ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
    "investimentos_curto": ["Other Short Term Investments"],
    "patrimonio": ["Stockholders Equity", "Total Equity Gross Minority Interest"],
    "ativos": ["Total Assets"],
}

# Faixas de plausibilidade por campo (US$ milhoes, ou % / x conforme o caso).
FAIXAS: dict[str, tuple[float, float]] = {
    "receita": (1_000.0, 500_000.0),
    "lucro_liquido": (-50_000.0, 60_000.0),
    "ebitda": (-20_000.0, 120_000.0),
    "margem_liquida_pct": (-100.0, 60.0),
    "fluxo_caixa_operacional": (-20_000.0, 120_000.0),
    "fcf": (-40_000.0, 90_000.0),
    "capex": (-60_000.0, 0.0),
    "divida_liquida": (-150_000.0, 300_000.0),
    "divida_patrimonio_pct": (0.0, 400.0),
    "roe_pct": (-100.0, 100.0),
    "roa_pct": (-60.0, 60.0),
}

TOLERANCIA_COERENCIA = 0.02  # 2% de folga nas identidades contabeis


# ---------------------------------------------------------------------------
# Rotulo de periodo
# ---------------------------------------------------------------------------
def rotulo_trimestre(fim: date) -> str:
    """"Q2 2026" -- o formato que o JSON ja usa em q_recente.trimestre."""
    return f"Q{(fim.month - 1) // 3 + 1} {fim.year}"


def rotulo_historico(trimestre: str) -> str:
    """"Q2 2026" -> "2026-Q2".

    O grafico de series historicas ordena os periodos como texto. "Q1 2026"
    ordenaria antes de "Q2 2025", embaralhando a linha do tempo; "2026-Q1"
    ordena certo sem precisar de logica extra no dashboard.
    """
    m = re.fullmatch(r"Q([1-4])\s+(\d{4})", trimestre.strip())
    if not m:
        return trimestre
    return f"{m.group(2)}-Q{m.group(1)}"


def ordem_trimestre(trimestre: str) -> tuple[int, int]:
    """Chave de ordenacao cronologica. Aceita "Q2 2026" e "2026-Q2"."""
    m = re.fullmatch(r"Q([1-4])\s+(\d{4})", trimestre.strip())
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.fullmatch(r"(\d{4})-Q([1-4])", trimestre.strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    return (0, 0)


def e_mais_novo(candidato: str, atual: str) -> bool:
    return ordem_trimestre(candidato) > ordem_trimestre(atual)


# ---------------------------------------------------------------------------
# Relatorio
# ---------------------------------------------------------------------------
@dataclass
class Relatorio:
    novos: list[dict[str, Any]] = field(default_factory=list)
    sem_novidade: list[dict[str, Any]] = field(default_factory=list)
    divergencias: list[dict[str, Any]] = field(default_factory=list)
    rejeicoes: list[dict[str, Any]] = field(default_factory=list)
    falhas: list[dict[str, Any]] = field(default_factory=list)

    def resumo(self) -> str:
        linhas: list[str] = []
        if self.novos:
            linhas.append(f"{len(self.novos)} empresa(s) com trimestre novo:")
            for n in self.novos:
                linhas.append(
                    f"  {n['ticker']:<5} {n['de']} -> {n['para']}"
                    f"  (receita {n['receita']:,.0f} | lucro {n['lucro_liquido']:,.0f})".replace(",", ".")
                )
        else:
            linhas.append("Nenhum trimestre novo divulgado.")
        for rotulo, itens, titulo in (
            ("rejeicoes", self.rejeicoes, "campo(s) rejeitado(s)"),
            ("divergencias", self.divergencias, "divergencia(s) com o dado curado"),
            ("falhas", self.falhas, "empresa(s) sem dado"),
        ):
            if itens:
                linhas.append(f"{len(itens)} {titulo}:")
                for i in itens:
                    detalhe = i.get("motivo") or i.get("detalhe", "")
                    linhas.append(f"  {i['ticker']:<5} {i.get('campo', '')} {detalhe}")
        return "\n".join(linhas)

    def para_json(self) -> dict[str, Any]:
        return {
            "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "novos": self.novos,
            "sem_novidade": self.sem_novidade,
            "divergencias": self.divergencias,
            "rejeicoes": self.rejeicoes,
            "falhas": self.falhas,
        }


# ---------------------------------------------------------------------------
# Camada de rede (unico ponto que fala com a internet)
# ---------------------------------------------------------------------------
def busca_fundamentos(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """Le as demonstracoes trimestrais de cada ticker via yfinance.

    Devolve {ticker: {"fim": date, "linhas": {chave: valor}}} com os valores ja
    em US$ milhoes. Ticker ausente = falha; nunca levanta por ticker isolado.
    """
    try:
        import yfinance  # type: ignore
    except ImportError:  # pragma: no cover - ambiente sem a dependencia
        raise SystemExit("yfinance nao instalado. Rode: pip install -r requirements-market.txt")

    saida: dict[str, dict[str, Any]] = {}
    for ticker in tickers:
        try:
            papel = yfinance.Ticker(ticker)
            bruto = coleta_bruto(
                papel.quarterly_income_stmt,
                papel.quarterly_cashflow,
                papel.quarterly_balance_sheet,
            )
        except Exception as exc:  # pragma: no cover - depende da rede
            print(f"  ! {ticker}: falha ao consultar ({exc.__class__.__name__}: {exc})")
            continue
        if bruto:
            saida[ticker] = bruto
    return saida


def _valor(df, chaves: list[str], coluna) -> float | None:
    """Primeiro rotulo presente no DataFrame, na coluna pedida."""
    if df is None or getattr(df, "empty", True):
        return None
    for chave in chaves:
        if chave in df.index:
            try:
                v = df.loc[chave, coluna]
            except (KeyError, IndexError):
                continue
            if v is None:
                continue
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if f == f:  # descarta NaN
                return f
    return None


def coleta_bruto(income, cashflow, balance) -> dict[str, Any] | None:
    """Extrai a coluna mais recente das tres demonstracoes, em US$ milhoes."""
    if income is None or getattr(income, "empty", True):
        return None
    coluna = income.columns[0]
    fim = coluna.date() if hasattr(coluna, "date") else coluna

    linhas: dict[str, float | None] = {}
    for chave, rotulos in LINHAS.items():
        fonte = income
        if chave in ("fco", "capex", "fcf"):
            fonte = cashflow
        elif chave in ("divida_total", "caixa", "investimentos_curto", "patrimonio", "ativos"):
            fonte = balance
        alvo = coluna if fonte is income else (fonte.columns[0] if fonte is not None and not getattr(fonte, "empty", True) else None)
        linhas[chave] = None if alvo is None else _valor(fonte, rotulos, alvo)

    # Lucro dos ultimos 12 meses, somando ate 4 colunas trimestrais. E o que
    # permite ROE e ROA em base anual, comparaveis com o ano fiscal ao lado.
    ttm_lucro = 0.0
    trimestres_somados = 0
    for col in list(income.columns)[:4]:
        v = _valor(income, LINHAS["lucro_liquido"], col)
        if v is None:
            break
        ttm_lucro += v
        trimestres_somados += 1

    # Trimestres anteriores, para preencher a serie historica de uma vez.
    # Sem isso a secao de series so ficaria util depois de um ano de coleta,
    # capturando um trimestre por execucao.
    anteriores = []
    for col in list(income.columns)[1:]:
        fim_ant = col.date() if hasattr(col, "date") else col
        linhas_ant = {}
        for chave, rotulos in LINHAS.items():
            fonte = income
            if chave in ("fco", "capex", "fcf"):
                fonte = cashflow
            elif chave in ("divida_total", "caixa", "investimentos_curto", "patrimonio", "ativos"):
                fonte = balance
            v = _valor(fonte, rotulos, col) if fonte is not None else None
            linhas_ant[chave] = v / 1e6 if v is not None else None
        if linhas_ant.get("receita") is not None:
            anteriores.append({"fim": fim_ant, "linhas": linhas_ant, "ttm": {}})

    # Demonstracoes vem em unidades; o JSON guarda US$ milhoes.
    return {
        "fim": fim,
        "linhas": {k: (v / 1e6 if v is not None else None) for k, v in linhas.items()},
        "ttm": ({"lucro_liquido": ttm_lucro / 1e6} if trimestres_somados == 4 else {}),
        "anteriores": anteriores,
    }


# ---------------------------------------------------------------------------
# Traducao para o formato do JSON (funcao pura)
# ---------------------------------------------------------------------------
def monta_trimestre(bruto: dict[str, Any], ttm: dict[str, float] | None = None) -> dict[str, Any]:
    """Converte as linhas das demonstracoes nos campos do nosso JSON."""
    L = bruto["linhas"]
    receita = L.get("receita")
    lucro = L.get("lucro_liquido")

    ebitda = L.get("ebitda")
    if ebitda is None and L.get("ebit") is not None and L.get("depreciacao") is not None:
        # Caminho de reserva: nem toda empresa publica EBITDA como linha.
        ebitda = L["ebit"] + L["depreciacao"]

    capex = L.get("capex")
    if capex is not None:
        capex = -abs(capex)  # o JSON guarda capex negativo

    fco = L.get("fco")
    fcf = L.get("fcf")
    if fcf is None and fco is not None and capex is not None:
        fcf = fco + capex

    caixa = (L.get("caixa") or 0.0) + (L.get("investimentos_curto") or 0.0)
    divida_liquida = None
    if L.get("divida_total") is not None:
        divida_liquida = L["divida_total"] - caixa

    divida_patrimonio = None
    if L.get("divida_total") is not None and L.get("patrimonio"):
        divida_patrimonio = L["divida_total"] / L["patrimonio"] * 100

    margem = None
    if receita and lucro is not None:
        margem = lucro / receita * 100

    # ROE e ROA em base anual (lucro dos ultimos 12 meses). Sem o TTM, o
    # trimestre isolado produziria um retorno ~4x menor e incomparavel com o
    # ano fiscal exibido ao lado.
    lucro_ttm = (ttm or {}).get("lucro_liquido")
    roe = roa = None
    if lucro_ttm is not None:
        if L.get("patrimonio"):
            roe = lucro_ttm / L["patrimonio"] * 100
        if L.get("ativos"):
            roa = lucro_ttm / L["ativos"] * 100

    return {
        "trimestre": rotulo_trimestre(bruto["fim"]),
        "receita": _arredonda(receita, 0),
        "lucro_liquido": _arredonda(lucro, 0),
        "ebitda": _arredonda(ebitda, 0),
        "margem_liquida_pct": _arredonda(margem, 2),
        "fluxo_caixa_operacional": _arredonda(fco, 0),
        "fcf": _arredonda(fcf, 0),
        "capex": _arredonda(capex, 0),
        "divida_liquida": _arredonda(divida_liquida, 0),
        "divida_patrimonio_pct": _arredonda(divida_patrimonio, 1),
        "roe_pct": _arredonda(roe, 2),
        "roa_pct": _arredonda(roa, 2),
    }


def _arredonda(v: float | None, casas: int) -> float | int | None:
    if v is None:
        return None
    return int(round(v)) if casas == 0 else round(v, casas)


# ---------------------------------------------------------------------------
# Validacao
# ---------------------------------------------------------------------------
def valida_campos(bloco: dict[str, Any]) -> list[tuple[str, str]]:
    """Faixa de plausibilidade campo a campo. Devolve [(campo, motivo)]."""
    problemas = []
    for campo, (minimo, maximo) in FAIXAS.items():
        v = bloco.get(campo)
        if v is None:
            continue
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v != v:
            problemas.append((campo, "valor nao numerico"))
        elif not (minimo <= v <= maximo):
            problemas.append((campo, f"fora da faixa [{minimo:g}, {maximo:g}]: {v}"))
    return problemas


def valida_coerencia(bloco: dict[str, Any]) -> list[str]:
    """Identidades que as demonstracoes tem de respeitar entre si.

    E a checagem que pega o erro perigoso: um numero plausivel no campo errado.
    """
    avisos: list[str] = []
    receita = bloco.get("receita")
    ebitda = bloco.get("ebitda")
    lucro = bloco.get("lucro_liquido")
    fco = bloco.get("fluxo_caixa_operacional")
    capex = bloco.get("capex")
    fcf = bloco.get("fcf")
    margem = bloco.get("margem_liquida_pct")

    if receita is not None and ebitda is not None and ebitda > receita:
        avisos.append(f"EBITDA ({ebitda}) maior que a receita ({receita})")
    if receita is not None and lucro is not None and lucro > receita:
        avisos.append(f"lucro ({lucro}) maior que a receita ({receita})")
    if None not in (fco, capex, fcf):
        esperado = fco + capex
        if abs(esperado) > 1 and abs(fcf - esperado) / max(abs(esperado), 1) > TOLERANCIA_COERENCIA:
            avisos.append(f"FCF ({fcf}) nao bate com FCO + capex ({esperado:.0f})")
    if None not in (receita, lucro, margem) and receita:
        esperado = lucro / receita * 100
        if abs(margem - esperado) > 0.5:
            avisos.append(f"margem ({margem}%) nao bate com lucro/receita ({esperado:.2f}%)")
    if capex is not None and capex > 0:
        avisos.append(f"capex positivo ({capex}); o JSON guarda capex negativo")
    return avisos


# ---------------------------------------------------------------------------
# Aplicacao
# ---------------------------------------------------------------------------
def aplica_fundamentos(
    dados: dict[str, Any],
    coletado: dict[str, dict[str, Any]],
    hoje: date | None = None,
) -> tuple[dict[str, Any], Relatorio]:
    """Monta o JSON novo. Nao escreve em disco.

    Devolve (dados_atualizados, relatorio). O dicionario de entrada nao e
    modificado.
    """
    hoje = hoje or date.today()
    rel = Relatorio()
    saida = json.loads(json.dumps(dados))  # copia profunda

    for empresa in saida["empresas"]:
        ticker = empresa["ticker"]
        atual = empresa["q_recente"]

        bruto = coletado.get(ticker)
        if not bruto:
            rel.falhas.append({"ticker": ticker, "detalhe": "sem resposta da fonte; bloco mantido"})
            continue

        novo = monta_trimestre(bruto, ttm=bruto.get("ttm"))
        rotulo = novo["trimestre"]

        if not e_mais_novo(rotulo, atual["trimestre"]):
            # Mesmo trimestre: nao sobrescreve, mas confere e reporta.
            for campo in ("receita", "lucro_liquido", "ebitda"):
                antes, depois = atual.get(campo), novo.get(campo)
                if None in (antes, depois) or not antes:
                    continue
                if abs(depois - antes) / abs(antes) > 0.05:
                    rel.divergencias.append({
                        "ticker": ticker, "campo": campo, "curado": antes, "fonte": depois,
                        "motivo": f"curado {antes} vs fonte {depois} (>5%)",
                    })
            rel.sem_novidade.append({"ticker": ticker, "trimestre": atual["trimestre"]})
            continue

        problemas = valida_campos(novo)
        for campo, motivo in problemas:
            rel.rejeicoes.append({"ticker": ticker, "campo": campo, "motivo": motivo})
            novo[campo] = None

        incoerencias = valida_coerencia(novo)
        if incoerencias:
            for aviso in incoerencias:
                rel.rejeicoes.append({"ticker": ticker, "campo": "coerencia", "motivo": aviso})
            # Coerencia quebrada derruba a empresa inteira: e sinal de que a
            # fonte mudou de formato, e meio balanco errado e pior que nenhum.
            rel.falhas.append({"ticker": ticker, "detalhe": "demonstracoes incoerentes; trimestre descartado"})
            continue

        if novo.get("receita") is None or novo.get("lucro_liquido") is None:
            rel.falhas.append({"ticker": ticker, "detalhe": "receita ou lucro ausentes; trimestre descartado"})
            continue

        # Producao nao sai de demonstracao financeira: preserva e marca.
        novo["producao_kboed"] = atual.get("producao_kboed")

        historico = list(empresa.get("historico") or [])
        ja_tem = {h.get("periodo") for h in historico}

        # O trimestre que sai de q_recente e o dado CURADO: entra sempre e tem
        # precedencia sobre a versao da fonte, se as duas existirem.
        saindo = _para_historico(atual)
        historico = [h for h in historico if h.get("periodo") != saindo["periodo"]]
        historico.append(saindo)
        ja_tem.add(saindo["periodo"])

        # Backfill: trimestres anteriores que a fonte trouxe e ainda nao temos.
        for anterior in bruto.get("anteriores") or []:
            candidato = monta_trimestre(anterior)
            periodo = rotulo_historico(candidato["trimestre"])
            if periodo in ja_tem:
                continue
            if not e_mais_novo(rotulo, candidato["trimestre"]):
                continue  # nao guarda no historico algo igual ou mais novo que q_recente
            if valida_coerencia(candidato) or candidato.get("receita") is None:
                continue  # backfill e conveniencia: na duvida, nao entra
            historico.append(_para_historico(candidato))
            ja_tem.add(periodo)

        historico.sort(key=lambda h: ordem_trimestre(h.get("periodo", "")))
        empresa["historico"] = historico

        empresa["q_recente"] = {c: novo.get(c, atual.get(c)) for c in CAMPOS_TRIMESTRE}
        empresa["proveniencia"] = {
            "fundamentos": {
                "fonte": "Yahoo Finance (demonstracoes trimestrais)",
                "coletado_em": hoje.isoformat(),
                "campos": CAMPOS_DERIVAVEIS,
            },
            "producao_kboed": {
                "fonte": "release da empresa",
                "trimestre_do_dado": atual["trimestre"],
                "observacao": "carregado do trimestre anterior; atualizar a mao com o release",
            },
        }

        rel.novos.append({
            "ticker": ticker, "de": atual["trimestre"], "para": rotulo,
            "receita": novo["receita"], "lucro_liquido": novo["lucro_liquido"],
        })

    return saida, rel


def _para_historico(bloco: dict[str, Any]) -> dict[str, Any]:
    """Converte um q_recente no formato de item de `historico`."""
    return {
        "periodo": rotulo_historico(bloco.get("trimestre", "")),
        "receita": bloco.get("receita"),
        "lucro_liquido": bloco.get("lucro_liquido"),
        "ebitda": bloco.get("ebitda"),
        "fluxo_caixa_operacional": bloco.get("fluxo_caixa_operacional"),
        "fcf": bloco.get("fcf"),
        "capex": bloco.get("capex"),
        "divida_liquida": bloco.get("divida_liquida"),
        "producao_kboed": bloco.get("producao_kboed"),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="mostra o que mudaria, sem escrever")
    parser.add_argument("--relatorio", type=Path, help="grava o relatorio em JSON")
    parser.add_argument("--json", type=Path, default=JSON_DADOS, help="caminho do arquivo de dados")
    args = parser.parse_args(argv)

    dados = json.loads(args.json.read_text(encoding="utf-8"))
    tickers = [e["ticker"] for e in dados["empresas"]]

    print(f"Consultando demonstracoes de {len(tickers)} tickers: {', '.join(tickers)}")
    coletado = busca_fundamentos(tickers)

    saida, rel = aplica_fundamentos(dados, coletado)
    print(rel.resumo())

    if args.relatorio:
        args.relatorio.write_text(
            json.dumps(rel.para_json(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    if not rel.novos:
        return 0

    if args.dry_run:
        print("\n--dry-run: arquivo NAO foi escrito.")
        return 0

    # Fundamentos mudam o arquivo inteiro de formato, entao aqui vale
    # reserializar -- ao contrario do update_market_data, que e cirurgico.
    args.json.write_text(json.dumps(saida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{args.json.name} atualizado com {len(rel.novos)} trimestre(s) novo(s).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
