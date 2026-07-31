#!/usr/bin/env python3
"""Atualiza os dados de MERCADO do indicadores_oleo_gas.json.

Campos atualizados (bloco "mercado" de cada empresa):
    preco_acao, market_cap, pe, dividend_yield_pct, ev_ebitda

Os dados FUNDAMENTAIS (receita, EBITDA, capex, divida liquida, producao...)
NAO sao tocados: continuam curados a mao a cada balanco. Esta rotina cuida
apenas do que muda todo dia por causa do preco da acao.

Principios de projeto
---------------------
1. Fail-safe. Se um campo nao passa na validacao, o valor ANTERIOR e mantido
   e a rejeicao e reportada. Nunca se escreve um numero suspeito por cima de
   um numero bom.
2. Diff minimo. O JSON e curado a mao, com objetos compactos de uma linha.
   Reserializar com json.dump() inflaria o arquivo de 11 KB para 13 KB e
   trocaria todas as linhas. Por isso a escrita e uma substituicao cirurgica
   de texto: um commit diario mexe em ~9 linhas, e o historico continua legivel.
3. Rede isolada. Toda a rede vive em `busca_cotacoes`. O resto do modulo e
   funcao pura, testavel sem internet (ver tests/test_update_market.py).

Uso:
    python3 update_market_data.py                 # atualiza o JSON
    python3 update_market_data.py --dry-run       # so mostra o que mudaria
    python3 update_market_data.py --forcar        # ignora o limite de variacao
    python3 update_market_data.py --relatorio r.json
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

# Ordem das chaves dentro do bloco "mercado", preservada na reescrita.
ORDEM_MERCADO = ["market_cap", "pe", "ev_ebitda", "dividend_yield_pct", "preco_acao"]

# Faixas de plausibilidade. Valor fora da faixa e tratado como dado corrompido
# da fonte (simbolo errado, campo ausente virando zero, etc).
FAIXAS: dict[str, tuple[float, float]] = {
    "preco_acao": (1.0, 10_000.0),
    "market_cap": (1_000.0, 5_000_000.0),   # US$ milhoes
    "pe": (0.5, 200.0),
    "dividend_yield_pct": (0.0, 25.0),
    "ev_ebitda": (0.5, 60.0),
}

# Variacao maxima aceita em relacao ao valor anterior, por atualizacao.
# Protege contra desdobramento de acoes, troca de simbolo e erro de unidade:
# nesses casos o numero "novo" e valido isoladamente, mas pula de patamar.
#
# ATENCAO ao efeito colateral: como o valor anterior nunca avanca quando a
# rejeicao acontece, um movimento REAL acima do limite (split, crash, mudanca
# de politica de dividendos) congela o campo para sempre -- toda execucao
# seguinte compara com a mesma base velha e rejeita de novo. Por isso existe
# o --forcar, e por isso o relatorio traz as rejeicoes explicitamente.
VARIACAO_MAX: dict[str, float] = {
    "preco_acao": 0.40,
    "market_cap": 0.40,
    "pe": 0.70,
    "dividend_yield_pct": 0.60,
    "ev_ebitda": 0.70,
}

# Campos que sao decimais com 2 casas; market_cap fica inteiro (US$ milhoes).
DECIMAIS = {"pe": 2, "ev_ebitda": 2, "dividend_yield_pct": 2, "preco_acao": 2}


# ---------------------------------------------------------------------------
# Relatorio
# ---------------------------------------------------------------------------
@dataclass
class Relatorio:
    """Acumula o que mudou, o que foi rejeitado e o que falhou."""

    mudancas: list[dict[str, Any]] = field(default_factory=list)
    rejeicoes: list[dict[str, Any]] = field(default_factory=list)
    falhas: list[dict[str, Any]] = field(default_factory=list)
    tickers_ok: list[str] = field(default_factory=list)

    def mudou(self, ticker: str, campo: str, antes: float, depois: float) -> None:
        var = ((depois - antes) / abs(antes) * 100) if antes else None
        self.mudancas.append(
            {"ticker": ticker, "campo": campo, "antes": antes, "depois": depois, "var_pct": var}
        )

    def rejeitou(self, ticker: str, campo: str, valor: Any, motivo: str, mantido: Any) -> None:
        self.rejeicoes.append(
            {"ticker": ticker, "campo": campo, "valor": valor, "motivo": motivo, "mantido": mantido}
        )

    def falhou(self, ticker: str, motivo: str) -> None:
        self.falhas.append({"ticker": ticker, "motivo": motivo})

    def resumo(self) -> str:
        linhas: list[str] = []
        if self.mudancas:
            linhas.append(f"{len(self.mudancas)} valor(es) atualizado(s):")
            for m in sorted(self.mudancas, key=lambda x: (x["ticker"], x["campo"])):
                var = f" ({m['var_pct']:+.2f}%)" if m["var_pct"] is not None else ""
                linhas.append(f"  {m['ticker']:<5} {m['campo']:<20} {m['antes']} -> {m['depois']}{var}")
        else:
            linhas.append("Nenhum valor mudou.")
        if self.rejeicoes:
            linhas.append(f"{len(self.rejeicoes)} valor(es) rejeitado(s) (mantido o anterior):")
            for r in self.rejeicoes:
                linhas.append(f"  {r['ticker']:<5} {r['campo']:<20} {r['valor']!r}: {r['motivo']}")
        if self.falhas:
            linhas.append(f"{len(self.falhas)} ticker(s) sem dado:")
            for f_ in self.falhas:
                linhas.append(f"  {f_['ticker']:<5} {f_['motivo']}")
        return "\n".join(linhas)

    def para_json(self) -> dict[str, Any]:
        return {
            "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tickers_ok": self.tickers_ok,
            "mudancas": self.mudancas,
            "rejeicoes": self.rejeicoes,
            "falhas": self.falhas,
        }


# ---------------------------------------------------------------------------
# Camada de rede (unico ponto que fala com a internet)
# ---------------------------------------------------------------------------
def busca_cotacoes(tickers: list[str]) -> dict[str, dict[str, float | None]]:
    """Busca dados de mercado no Yahoo Finance via yfinance.

    Devolve {ticker: {campo: valor|None}}. Ticker ausente do dicionario =
    falha total naquele simbolo. Nao levanta excecao por ticker individual:
    uma indisponibilidade pontual nao pode derrubar a rotina inteira.
    """
    try:
        import yfinance  # type: ignore
    except ImportError:  # pragma: no cover - ambiente sem a dependencia
        raise SystemExit(
            "yfinance nao instalado. Rode: pip install -r requirements-market.txt"
        )

    saida: dict[str, dict[str, float | None]] = {}
    for ticker in tickers:
        try:
            info = yfinance.Ticker(ticker).info or {}
        except Exception as exc:  # pragma: no cover - depende da rede
            print(f"  ! {ticker}: falha ao consultar ({exc.__class__.__name__}: {exc})")
            continue
        if not info:  # pragma: no cover - depende da rede
            print(f"  ! {ticker}: resposta vazia")
            continue
        saida[ticker] = extrai_campos(info)
    return saida


def _primeiro(info: dict[str, Any], *chaves: str) -> float | None:
    """Primeiro valor numerico presente entre varias chaves alternativas."""
    for chave in chaves:
        valor = info.get(chave)
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            return float(valor)
    return None


def normaliza_yield(info: dict[str, Any], preco: float | None) -> float | None:
    """Devolve o dividend yield em pontos percentuais.

    O yfinance ja devolveu esse campo como fracao (0.0278) em umas versoes e
    como percentual (2.78) em outras -- e um erro classico de 100x. Por isso a
    ordem de preferencia comeca pelo calculo explicito a partir do dividendo
    anual, que nao tem ambiguidade de unidade.
    """
    taxa = _primeiro(info, "trailingAnnualDividendRate", "dividendRate")
    if taxa is not None and preco:
        return taxa / preco * 100

    # trailingAnnualDividendYield e sempre fracao.
    fracao = _primeiro(info, "trailingAnnualDividendYield")
    if fracao is not None:
        return fracao * 100

    bruto = _primeiro(info, "dividendYield")
    if bruto is None:
        return None
    # Desambiguacao por magnitude: nenhuma major de oleo e gas paga menos de
    # 0,5% nem mais de 50%, entao <= 0.5 so pode ser fracao.
    return bruto * 100 if bruto <= 0.5 else bruto


def extrai_campos(info: dict[str, Any]) -> dict[str, float | None]:
    """Traduz o dicionario cru do Yahoo para o formato do nosso JSON."""
    preco = _primeiro(info, "regularMarketPrice", "currentPrice", "previousClose")
    market_cap = _primeiro(info, "marketCap")
    return {
        "preco_acao": preco,
        # Yahoo devolve market cap em unidades; nosso JSON guarda US$ milhoes.
        "market_cap": market_cap / 1e6 if market_cap is not None else None,
        "pe": _primeiro(info, "trailingPE"),
        "dividend_yield_pct": normaliza_yield(info, preco),
        "ev_ebitda": _primeiro(info, "enterpriseToEbitda"),
    }


# ---------------------------------------------------------------------------
# Validacao e arredondamento (funcoes puras)
# ---------------------------------------------------------------------------
def arredonda(campo: str, valor: float) -> float | int:
    if campo == "market_cap":
        return int(round(valor))
    return round(valor, DECIMAIS.get(campo, 2))


def valida(campo: str, novo: Any, anterior: Any, forcar: bool = False) -> tuple[bool, str]:
    """Decide se `novo` pode substituir `anterior`. Devolve (aceito, motivo).

    Com `forcar`, a faixa de plausibilidade continua valendo mas o limite de
    variacao e ignorado -- e a saida para destravar um campo congelado depois
    de um movimento real grande (split, crash, corte de dividendo).
    """
    if novo is None:
        return False, "campo ausente na resposta da fonte"
    if not isinstance(novo, (int, float)) or isinstance(novo, bool):
        return False, f"tipo inesperado ({type(novo).__name__})"
    if novo != novo or novo in (float("inf"), float("-inf")):  # NaN / infinito
        return False, "valor nao finito"

    minimo, maximo = FAIXAS[campo]
    if not (minimo <= novo <= maximo):
        return False, f"fora da faixa plausivel [{minimo:g}, {maximo:g}]"

    if not forcar and isinstance(anterior, (int, float)) and anterior:
        variacao = abs(novo - anterior) / abs(anterior)
        limite = VARIACAO_MAX[campo]
        if variacao > limite:
            return False, (
                f"variacao de {variacao * 100:.1f}% acima do limite de "
                f"{limite * 100:.0f}% (possivel split, troca de simbolo ou erro de unidade). "
                "Se o movimento for real, rode com --forcar"
            )
    return True, ""


def aplica_cotacoes(
    dados: dict[str, Any],
    cotacoes: dict[str, dict[str, float | None]],
    forcar: bool = False,
) -> tuple[dict[str, dict[str, float | int]], Relatorio]:
    """Calcula o novo bloco "mercado" de cada empresa. Nao escreve nada em disco.

    Devolve ({ticker: bloco_mercado_final}, relatorio).
    """
    rel = Relatorio()
    finais: dict[str, dict[str, float | int]] = {}

    for empresa in dados["empresas"]:
        ticker = empresa["ticker"]
        atual = dict(empresa["mercado"])
        finais[ticker] = atual

        recebido = cotacoes.get(ticker)
        if not recebido:
            rel.falhou(ticker, "sem resposta da fonte; bloco mantido integralmente")
            continue

        houve_campo_valido = False
        for campo in ORDEM_MERCADO:
            bruto = recebido.get(campo)
            anterior = atual.get(campo)
            ok, motivo = valida(campo, bruto, anterior, forcar=forcar)
            if not ok:
                if bruto is not None:
                    rel.rejeitou(ticker, campo, bruto, motivo, anterior)
                continue
            houve_campo_valido = True
            novo = arredonda(campo, float(bruto))
            if novo != anterior:
                rel.mudou(ticker, campo, anterior, novo)
                atual[campo] = novo

        if houve_campo_valido:
            rel.tickers_ok.append(ticker)
        else:
            rel.falhou(ticker, "nenhum campo passou na validacao; bloco mantido")

    return finais, rel


# ---------------------------------------------------------------------------
# Escrita cirurgica no JSON (preserva a formatacao curada a mao)
# ---------------------------------------------------------------------------
def _formata_numero(campo: str, valor: float | int) -> str:
    """Reproduz o estilo do arquivo: market cap inteiro, o resto com 2 casas fixas.

    O JSON curado escreve "ev_ebitda": 6.00 e "preco_acao": 42.00 -- com o zero
    a direita. repr() devolveria 6.0 e 42.0 e sujaria o diff de linhas que nao
    mudaram de valor.
    """
    if campo == "market_cap":
        return str(int(round(float(valor))))
    return f"{float(valor):.{DECIMAIS.get(campo, 2)}f}"


def serializa_mercado(bloco: dict[str, float | int]) -> str:
    partes = [f'"{c}": {_formata_numero(c, bloco[c])}' for c in ORDEM_MERCADO if c in bloco]
    # Preserva eventuais chaves extras que nao estejam na ordem canonica.
    partes += [f'"{c}": {json.dumps(v, ensure_ascii=False)}' for c, v in bloco.items() if c not in ORDEM_MERCADO]
    return "{" + ", ".join(partes) + "}"


_RE_MERCADO = re.compile(r'("mercado":\s*)\{[^{}]*\}')
_RE_TICKER = re.compile(r'"ticker":\s*"([A-Z.]+)"')


def reescreve_json(bruto: str, finais: dict[str, dict[str, float | int]]) -> str:
    """Substitui apenas as linhas "mercado" de cada empresa, na ordem do arquivo."""
    posicoes = [(m.group(1), m.end()) for m in _RE_TICKER.finditer(bruto)]
    if not posicoes:
        raise ValueError("nenhum ticker encontrado no JSON; formato inesperado")

    saida = bruto
    # De tras para frente: assim os offsets ja calculados nao se deslocam.
    for ticker, fim_ticker in reversed(posicoes):
        if ticker not in finais:
            continue
        alvo = _RE_MERCADO.search(saida, fim_ticker)
        if alvo is None:
            raise ValueError(f'bloco "mercado" nao encontrado para {ticker}')
        saida = saida[: alvo.start()] + alvo.group(1) + serializa_mercado(finais[ticker]) + saida[alvo.end():]
    return saida


def atualiza_datas(bruto: str, hoje: date) -> str:
    """Sincroniza a data de revisao e a nota que cita o snapshot de mercado."""
    iso, br = hoje.isoformat(), hoje.strftime("%d/%m/%Y")
    bruto = re.sub(r'("atualizado_em":\s*")\d{4}-\d{2}-\d{2}(")', rf"\g<1>{iso}\g<2>", bruto)
    bruto = re.sub(
        r"(snapshot' de mercado em )\d{2}/\d{2}/\d{4}", rf"\g<1>{br}", bruto
    )
    return bruto


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="mostra o que mudaria, sem escrever")
    parser.add_argument("--forcar", action="store_true",
                        help="ignora o limite de variacao (destrava campo congelado apos movimento real)")
    parser.add_argument("--relatorio", type=Path, help="grava o relatorio em JSON no caminho indicado")
    parser.add_argument("--json", type=Path, default=JSON_DADOS, help="caminho do arquivo de dados")
    args = parser.parse_args(argv)

    bruto = args.json.read_text(encoding="utf-8")
    dados = json.loads(bruto)
    tickers = [e["ticker"] for e in dados["empresas"]]

    print(f"Consultando {len(tickers)} tickers: {', '.join(tickers)}")
    cotacoes = busca_cotacoes(tickers)

    finais, rel = aplica_cotacoes(dados, cotacoes, forcar=args.forcar)
    print(rel.resumo())

    if args.relatorio:
        args.relatorio.write_text(
            json.dumps(rel.para_json(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    # Falha so quando NENHUM ticker respondeu: nesse caso a fonte caiu ou mudou
    # de formato, e e melhor o workflow ficar vermelho do que passar batido.
    if not rel.tickers_ok:
        print("\nERRO: nenhum ticker retornou dado valido. Arquivo nao foi alterado.", file=sys.stderr)
        return 1

    if not rel.mudancas:
        print("\nNada a escrever.")
        return 0

    novo = atualiza_datas(reescreve_json(bruto, finais), date.today())

    # Rede de seguranca: o texto reescrito tem de continuar sendo JSON valido e
    # so pode diferir do original nos campos de mercado e nas datas.
    conferido = json.loads(novo)
    # zip() truncaria em silencio se a reescrita comesse uma empresa.
    if len(dados["empresas"]) != len(conferido["empresas"]):
        raise AssertionError(
            f"reescrita mudou o numero de empresas: {len(dados['empresas'])} -> {len(conferido['empresas'])}"
        )
    # "producao_kboed" nao existe no nivel da empresa (vive dentro de fy2025 /
    # q_recente), entao a checagem antiga comparava None com None e nao valia nada.
    for antes, depois in zip(dados["empresas"], conferido["empresas"]):
        if antes.get("ticker") != depois.get("ticker"):
            raise AssertionError(
                f"reescrita trocou a ordem dos tickers: {antes.get('ticker')} -> {depois.get('ticker')}"
            )
        for chave in ("fy2025", "q_recente", "historico", "fontes", "nome", "pais", "ticker"):
            if antes.get(chave) != depois.get(chave):
                raise AssertionError(f"reescrita alterou campo nao-mercado em {antes['ticker']}: {chave}")

    if args.dry_run:
        print("\n--dry-run: arquivo NAO foi escrito.")
        return 0

    args.json.write_text(novo, encoding="utf-8")
    print(f"\n{args.json.name} atualizado.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
