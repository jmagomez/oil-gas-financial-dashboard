#!/usr/bin/env python3
"""Coleta automática dos trimestres de ExxonMobil e Chevron pela API XBRL da SEC.

Fonte: https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json (dados dos próprios
10-Q/10-K, com data de arquivamento). Não usa agregador.

Definições (iguais às da série da PoC; README, "Definições por empresa"):
    ebitda          = lucro antes de impostos + despesa de juros + DD&A (inclui impairments)
    capex           = − pagamentos por imobilizado (linha de caixa da empresa)
    fcf             = fco + capex
    divida_liquida  = dívida curta + dívida longa (com arrendamentos financeiros) − caixa

Trimestres: usa o fato de 3 meses quando existe; senão, diferença de acumulados no ano
(ex.: FCO do 2T = acumulado de 6 meses − acumulado de 3 meses; 4T = ano − 9 meses).

Limitação conhecida: a ExxonMobil não publica a linha "Sales and other operating revenue"
como conceito us-gaap sem dimensão; a receita dela continua vindo do release (o script
devolve None e diz isso). O FCO do 2T25 da Chevron só existe em acumulado.

Uso:
    python3 poc/coleta_sec_xbrl.py --verificar            # baixa da SEC e compara com poc/coleta/
    python3 poc/coleta_sec_xbrl.py --verificar --offline  # usa tests/fixtures/xbrl/ (sem rede)
    python3 poc/coleta_sec_xbrl.py --gravar               # grava poc/coleta/<TICKER>_xbrl.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
COLETA = RAIZ / "poc" / "coleta"
FIXTURES = RAIZ / "tests" / "fixtures" / "xbrl"
USER_AGENT = "oil-gas-financial-dashboard 60618813+jmagomez@users.noreply.github.com"  # a SEC exige nome e e-mail de contato (sem isso: HTTP 403)
DESDE = "2025-01-01"

# Conceitos us-gaap por campo, em ordem de preferência.
EMPRESAS = {
    "XOM": {
        "ciks": ["0000034088", "0002115436"],  # Exxon Mobil Corp e, a partir do 2T26, ExxonMobil Holdings Corp
        "fluxo": {
            "receita": [],  # linha "Sales and other operating revenue" não existe sem dimensão
            "lucro_liquido": ["NetIncomeLoss"],
            "lair": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"],
            "juros": ["InterestExpense"],
            "dda": ["DepreciationDepletionAndAmortization"],
            "fluxo_caixa_operacional": ["NetCashProvidedByUsedInOperatingActivities"],
            "pagamento_capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
        },
        "saldo": {
            "divida_curta": ["DebtCurrent"],
            "divida_longa": ["LongTermDebtAndCapitalLeaseObligations"],
            "caixa": ["CashAndCashEquivalentsAtCarryingValue"],
        },
    },
    "CVX": {
        "ciks": ["0000093410"],
        "fluxo": {
            "receita": ["RevenueFromContractWithCustomerExcludingAssessedTax"],
            "lucro_liquido": ["NetIncomeLoss"],
            "lair": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
            "juros": ["InterestExpenseDebt"],
            "dda": ["DepreciationDepletionAndAmortization"],
            "fluxo_caixa_operacional": ["NetCashProvidedByUsedInOperatingActivities"],
            "pagamento_capex": ["PaymentsToAcquireProductiveAssets"],
        },
        "saldo": {
            "divida_curta": ["ShortTermBorrowings"],
            "divida_longa": ["LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"],
            # a Chevron só etiqueta o caixa somado ao restrito: caixa = total − restrito
            "caixa_total": ["CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
            "restrito_curto": ["RestrictedCashCurrent"],
            "restrito_longo": ["RestrictedCashNoncurrent"],
        },
    },
}


# --------------------------------------------------------------------------- #
# Entrada: companyfacts (JSON da SEC) -> linhas compactas
# --------------------------------------------------------------------------- #
def baixa(cik: str) -> dict:
    # cabeçalhos pedidos pela SEC (Fair Access): identificação, gzip e Host
    req = urllib.request.Request(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                                 headers={"User-Agent": USER_AGENT, "Accept": "application/json",
                                          "Accept-Encoding": "gzip, deflate", "Host": "data.sec.gov"})
    with urllib.request.urlopen(req, timeout=60) as r:
        b = r.read()
        if r.headers.get("Content-Encoding") == "gzip" or b[:2] == b"\x1f\x8b":
            b = gzip.decompress(b)
        return json.loads(b.decode("utf-8"))


def linhas_de_companyfacts(cf: dict, conceitos: set[str]) -> list[dict]:
    """Uma linha por (conceito, início, fim), ficando com o arquivamento mais recente."""
    gaap = cf.get("facts", {}).get("us-gaap", {})
    melhor: dict[tuple, dict] = {}
    for c in conceitos:
        for f in gaap.get(c, {}).get("units", {}).get("USD", []):
            if f["end"] < DESDE or (f.get("start") and f["start"] < DESDE):
                continue
            k = (c, f.get("start", ""), f["end"])
            if k not in melhor or f["filed"] > melhor[k]["filed"]:
                melhor[k] = dict(conceito=c, inicio=f.get("start", ""), fim=f["end"], valor=f["val"] / 1e6,
                                 form=f.get("form", ""), filed=f["filed"], accn=f.get("accn", ""))
    return list(melhor.values())


def linhas_de_fixture(caminho: Path) -> list[dict]:
    out = []
    for l in caminho.read_text(encoding="utf-8").splitlines()[1:]:
        c, ini, fim, v, form, filed = l.split("|")
        out.append(dict(conceito=c, inicio=ini, fim=fim, valor=float(v), form=form, filed=filed, accn=""))
    return out


# --------------------------------------------------------------------------- #
# Trimestres
# --------------------------------------------------------------------------- #
def _fim_tri(p: str) -> str:
    ano, q = int(p[:4]), int(p[-1])
    return {1: f"{ano}-03-31", 2: f"{ano}-06-30", 3: f"{ano}-09-30", 4: f"{ano}-12-31"}[q]


def _ini_tri(p: str) -> str:
    ano, q = int(p[:4]), int(p[-1])
    return f"{ano}-{3 * q - 2:02d}-01"


def valor_fluxo(linhas: list[dict], conceitos: list[str], p: str):
    """Valor do trimestre: fato de 3 meses ou diferença de acumulados no ano."""
    for c in conceitos:
        idx = {(l["inicio"], l["fim"]): l["valor"] for l in linhas if l["conceito"] == c and l["inicio"]}
        if (_ini_tri(p), _fim_tri(p)) in idx:
            return idx[(_ini_tri(p), _fim_tri(p))], "3 meses"
        ano, q = p[:4], int(p[-1])
        ytd = idx.get((f"{ano}-01-01", _fim_tri(p)))
        if ytd is None:
            continue
        if q == 1:
            return ytd, "3 meses"
        ant = idx.get((f"{ano}-01-01", _fim_tri(f"{ano}-Q{q - 1}")))
        if ant is not None:
            return ytd - ant, f"acumulado {q * 3}m − {(q - 1) * 3}m"
    return None, "ausente"


def valor_saldo(linhas: list[dict], conceitos: list[str], p: str):
    for c in conceitos:
        for l in linhas:
            if l["conceito"] == c and not l["inicio"] and l["fim"] == _fim_tri(p):
                return l["valor"]
    return None


def trimestre(ticker: str, linhas: list[dict], p: str) -> dict:
    cfg = EMPRESAS[ticker]
    r, origem = {}, {}
    for campo, cs in cfg["fluxo"].items():
        r[campo], origem[campo] = valor_fluxo(linhas, cs, p)
    s = {campo: valor_saldo(linhas, cs, p) for campo, cs in cfg["saldo"].items()}
    if "caixa_total" in s:
        s["caixa"] = None if s["caixa_total"] is None else s["caixa_total"] - (s["restrito_curto"] or 0) - (s["restrito_longo"] or 0)
    ok = lambda *xs: all(x is not None for x in xs)  # noqa: E731
    out = dict(receita=r["receita"], lucro_liquido=r["lucro_liquido"],
               ebitda=r["lair"] + r["juros"] + r["dda"] if ok(r["lair"], r["juros"], r["dda"]) else None,
               fluxo_caixa_operacional=r["fluxo_caixa_operacional"],
               capex=-r["pagamento_capex"] if r["pagamento_capex"] is not None else None)
    out["fcf"] = out["fluxo_caixa_operacional"] + out["capex"] if ok(out["fluxo_caixa_operacional"], out["capex"]) else None
    out["divida_liquida"] = (s["divida_curta"] + s["divida_longa"] - s["caixa"]
                             if ok(s.get("divida_curta"), s.get("divida_longa"), s.get("caixa")) else None)
    out = {k: (round(v) if v is not None else None) for k, v in out.items()}
    out["componentes"] = {**{k: v for k, v in r.items()}, **{k: v for k, v in s.items()}}
    out["origem"] = origem
    return out


def periodos(ate: str) -> list[str]:
    out, a, q = [], 2025, 1
    while f"{a}-Q{q}" <= ate:
        out.append(f"{a}-Q{q}")
        a, q = (a + 1, 1) if q == 4 else (a, q + 1)
    return out


# --------------------------------------------------------------------------- #
# Verificação contra a coleta dos releases
# --------------------------------------------------------------------------- #
CAMPOS = ["receita", "lucro_liquido", "ebitda", "fluxo_caixa_operacional", "capex", "fcf", "divida_liquida"]


def compara(ticker: str, calc: dict[str, dict], tolerancia: float = 0.005) -> list[str]:
    col = json.loads((COLETA / f"{ticker}.json").read_text(encoding="utf-8"))["trimestres"]
    dif = []
    for p, v in calc.items():
        ref = col.get(p)
        if not ref:
            continue
        for c in CAMPOS:
            a, b = v.get(c), ref.get(c)
            if a is None or b is None:
                continue
            if abs(a - b) > max(2, tolerancia * abs(b)):
                dif.append(f"{ticker} {p} {c}: XBRL {a:,} vs release {b:,}")
    return dif


def coleta(ticker: str, offline: bool) -> list[dict]:
    cfg = EMPRESAS[ticker]
    conceitos = {c for grupo in ("fluxo", "saldo") for cs in cfg[grupo].values() for c in cs}
    linhas = []
    for cik in cfg["ciks"]:
        if offline:
            linhas += linhas_de_fixture(FIXTURES / f"CIK{cik}.txt")
        else:
            linhas += linhas_de_companyfacts(baixa(cik), conceitos)
    # mesmo fato em dois CIKs (reorganização da ExxonMobil): fica o arquivamento mais recente
    melhor = {}
    for l in linhas:
        k = (l["conceito"], l["inicio"], l["fim"])
        if k not in melhor or l["filed"] > melhor[k]["filed"]:
            melhor[k] = l
    return list(melhor.values())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ate", default="2026-Q2", help="último trimestre (AAAA-Qn)")
    ap.add_argument("--offline", action="store_true", help="usa tests/fixtures/xbrl em vez da API")
    ap.add_argument("--verificar", action="store_true", help="compara com poc/coleta/<TICKER>.json; sai com 1 se divergir")
    ap.add_argument("--gravar", action="store_true", help="grava poc/coleta/<TICKER>_xbrl.json")
    ap.add_argument("--tolerar-403", action="store_true",
                    help="HTTP 403 da SEC vira aviso 'não verificado' (a SEC bloqueia alguns IPs de nuvem)")
    a = ap.parse_args(argv)
    falhas, bloqueadas = [], []
    for t in EMPRESAS:
        try:
            linhas = coleta(t, a.offline)
        except urllib.error.HTTPError as e:
            if e.code == 403 and a.tolerar_403:
                bloqueadas.append(t)
                print(f"AVISO {t}: a SEC devolveu HTTP 403 a este servidor; {t} NÃO foi verificado nesta execução")
                continue
            raise
        calc = {p: trimestre(t, linhas, p) for p in periodos(a.ate)}
        for p, v in calc.items():
            print(t, p, {c: v[c] for c in CAMPOS})
        if a.verificar:
            falhas += compara(t, calc)
        if a.gravar:
            (COLETA / f"{t}_xbrl.json").write_text(json.dumps(
                dict(empresa=t, fonte="SEC XBRL companyfacts", coletado_em=date.today().isoformat(),
                     trimestres=calc), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if a.verificar:
        ok = [t for t in EMPRESAS if t not in bloqueadas]
        print("\n".join(falhas) or (f"XBRL confere com a coleta dos releases (tolerância 0,5%): {', '.join(ok)}" if ok
                                    else "Nenhuma empresa verificada: acesso à SEC bloqueado"))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
