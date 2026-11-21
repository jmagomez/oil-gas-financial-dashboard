#!/usr/bin/env python3
"""Brent medio por trimestre e por ano, da serie mensal da EIA.

POR QUE ISTO EXISTE. O dashboard comparava margens e US$/boe de 2026 com os de
2025 sem dizer que o petroleo era outro: Brent de ~US$ 69 no 3T25 e de ~US$ 96
no 3T26. EBITDA "+90% sobre o FY2025" e, em boa parte, preco -- e um leitor que
nao acompanha a commodity le como desempenho. O Brent do periodo de cada
empresa vai ao lado dos indicadores para separar as duas coisas.

Por que Brent e nao o preco realizado de cada empresa: o realizado nao e
comparavel entre as sete. A BP publica "total hydrocarbons, US$/boe" (56,16 no
3T26); a ExxonMobil, liquidos e gas separados; a Petrobras, Brent e derivados
no mercado interno. Sete definicoes lado a lado parecem uma regua e nao sao.
O Brent e um so, e a captura de cada empresa sobre ele aparece em US$/boe.

FONTE. EIA, serie RBRTE ("Europe Brent Spot Price FOB"), mensal, US$/bbl. A
EIA calcula a media mensal como media simples dos fechamentos diarios. O
trimestre aqui e a media simples dos TRES meses -- nao identica a media dos dias
(os meses tem pregoes diferentes), mas a diferenca e de centavos: 3T26 = 96,33
aqui e 96,99 na tabela de precos de referencia da BP (Dated Brent, Platts).

`brent/raw.txt` (AAAA-MM;valor) fica versionado pelo mesmo motivo da PTAX: quem
audita um numero refaz a conta sem depender de API.

Uso:
    python3 brent.py                # mostra a media por trimestre
    python3 brent.py --atualizar    # busca na EIA os meses que faltam
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ARQUIVO = RAIZ / "brent" / "raw.txt"
FONTE = "EIA, Europe Brent Spot Price FOB (RBRTE), media mensal"

URL = (
    "https://api.eia.gov/v2/petroleum/pri/spt/data/?api_key={chave}&frequency=monthly"
    "&data[0]=value&facets[series][]=RBRTE&start={inicio}"
    "&sort[0][column]=period&sort[0][direction]=asc"
)

# Faixa de plausibilidade de uma media mensal, em US$/bbl. Pega unidade
# trocada (centavos) e serie errada.
FAIXA = (5.0, 300.0)

_RE_TRI = re.compile(r"^(?:Q([1-4]) (\d{4})|(\d{4})-Q([1-4]))$")


def le(arquivo: Path = ARQUIVO) -> dict[str, float]:
    """{"2026-09": 114.16, ...} -- vazio se o arquivo nao existir."""
    if not arquivo.exists():
        return {}
    serie: dict[str, float] = {}
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        if not linha.strip() or linha.startswith("#"):
            continue
        mes, valor = linha.split(";")
        serie[mes.strip()] = float(valor)
    return serie


def _meses_do_trimestre(rotulo: str) -> list[str] | None:
    m = _RE_TRI.match(str(rotulo or "").strip())
    if not m:
        return None
    tri, ano = (int(m.group(1)), int(m.group(2))) if m.group(1) else (int(m.group(4)), int(m.group(3)))
    return [f"{ano}-{mes:02d}" for mes in range(3 * tri - 2, 3 * tri + 1)]


def _media(meses: list[str], serie: dict[str, float]) -> float | None:
    """Media dos meses pedidos -- ou None se faltar UM. Media de pedaco nao e media do periodo."""
    valores = [serie.get(m) for m in meses]
    if any(v is None for v in valores):
        return None
    return round(sum(valores) / len(valores), 2)


def media_trimestre(rotulo: str, serie: dict[str, float] | None = None) -> float | None:
    """Brent medio de "Q3 2026" ou "2026-Q3"."""
    meses = _meses_do_trimestre(rotulo)
    return None if meses is None else _media(meses, le() if serie is None else serie)


def media_ano(ano: int, serie: dict[str, float] | None = None) -> float | None:
    return _media([f"{ano}-{m:02d}" for m in range(1, 13)], le() if serie is None else serie)


def mescla(serie: dict[str, float], novos: list[dict]) -> tuple[dict[str, float], list[str]]:
    """Acrescenta meses da EIA. Nunca reescreve mes existente; rejeita fora de faixa."""
    saida = dict(serie)
    rejeitados: list[str] = []
    for item in novos:
        mes, valor = item.get("period"), item.get("value")
        if not mes or valor in (None, "") or mes in saida:
            continue
        v = float(valor)
        if not FAIXA[0] <= v <= FAIXA[1]:
            rejeitados.append(f"{mes}={v}")
            continue
        saida[mes] = v
    return saida, rejeitados


def grava(serie: dict[str, float], arquivo: Path = ARQUIVO) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text("".join(f"{m};{serie[m]:.2f}\n" for m in sorted(serie)), encoding="utf-8")


def atualiza() -> int:  # pragma: no cover - rede
    serie = le()
    inicio = max(serie) if serie else "2025-01"
    # Sem chave propria, a EIA aceita DEMO_KEY com limite baixo -- suficiente
    # para uma consulta por dia.
    url = URL.format(chave=os.environ.get("EIA_API_KEY") or "DEMO_KEY", inicio=inicio)
    with urllib.request.urlopen(url, timeout=30) as r:
        dados = json.load(r)["response"]["data"]
    nova, rejeitados = mescla(serie, [d for d in dados if d.get("series") == "RBRTE"])
    grava(nova)
    print(f"Brent: {len(nova) - len(serie)} mes(es) novo(s); ultimo {max(nova)}")
    for r in rejeitados:
        print(f"  rejeitado (fora de {FAIXA}): {r}")
    return 0


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--atualizar", action="store_true")
    args = p.parse_args(argv)
    if args.atualizar:
        return atualiza()
    serie = le()
    anos = sorted({int(m[:4]) for m in serie})
    for ano in anos:
        for q in range(1, 5):
            v = media_trimestre(f"{ano}-Q{q}", serie)
            if v is not None:
                print(f"{ano}-Q{q}  {v:7.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
