#!/usr/bin/env python3
"""Trimestres da Petrobras direto da CVM (ITR/DFP), convertidos pela PTAX.

POR QUE A PETROBRAS TEM COLETA PROPRIA

As outras seis saem do Yahoo em dolar. A Petrobras sai em REAIS -- e
`update_fundamentals.valida_moeda` passou a descartar o trimestre dela por isso,
corretamente. Descartar protege o arquivo, mas deixa a empresa parada no
trimestre antigo. Este modulo e o caminho que faltava: le a demonstracao que a
propria companhia entrega ao regulador e converte com regra declarada.

Fonte: Portal de Dados Abertos da CVM, demonstracoes CONSOLIDADAS.
    https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/{ITR,DFP}/DADOS/
Nao passa por agregador. O portal e regenerado semanalmente, entao um balanco
divulgado numa terca so aparece aqui no fim de semana seguinte.

DEFINICOES (R$ milhoes, antes da conversao)
    receita          3.01     Receita de venda de bens e/ou servicos
    lucro_liquido    3.11.01  Lucro atribuido aos socios da controladora
    ebitda           LAIR (3.07) - resultado financeiro (3.06) + D&A (DFC)
                     E a definicao da Resolucao CVM 156 e a que a companhia
                     divulga. No 1T25: 53.635 - 10.595 + 18.976 = 62.016.
    fco              6.01
    capex            DFC: aquisicoes de imobilizado e intangivel
    divida bruta     financiamentos + arrendamentos (circulante e nao circulante)
    disponibilidades caixa e equivalentes + titulos e aplicacoes de curto E de
                     longo prazo ("disponibilidades ajustadas", como a Petrobras
                     define). Sem os de longo prazo a divida liquida do 1T25
                     saia 1,4% acima da divulgada.
    dividendos       DFC de financiamento (6.03.xx): dividendos e JCP pagos aos
                     acionistas DA PETROBRAS -- nao os pagos a nao controladores,
                     porque o denominador do yield e o market cap da Petrobras.
    recompras        DFC de financiamento: recompra / aquisicao de acoes proprias.
                     Sem a linha na DFC, ZERO: a DFC entregue a CVM e completa,
                     e a Petrobras teria a linha se tivesse recomprado. (No
                     Yahoo a ausencia continua sendo "nao sei" -- la uma linha
                     renomeada some sem aviso.)
    patrimonio       2.03     Patrimonio liquido consolidado
    ativos           1        Ativo total

ATENCAO AO EBITDA. A definicao acima NAO e a do agregador que alimentava a
serie antiga da Petrobras: por trimestre as duas divergiam de -18% a +27%
(a do agregador soma de volta so a despesa de juros; a da CVM, o resultado
financeiro inteiro, que na Petrobras carrega variacao cambial). A que bate com
o que a empresa divulga em dolar e esta: 2T26 = US$ 18,6 bilhoes no release,
18.588 aqui, 19.283 no agregador.

TRIMESTRE ISOLADO. A DRE do ITR traz o trimestre isolado; a DFC so o acumulado
do ano, entao o trimestre e a diferenca de acumulados. O 4T sai da DFP (ano
inteiro menos nove meses).

Uso:
    python3 coleta_cvm.py                 # ultimo trimestre disponivel, em US$
    python3 coleta_cvm.py --periodo 2026-Q2
    python3 coleta_cvm.py --zip itr_2026.zip itr_2025.zip dfp_2025.zip
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import unicodedata
import urllib.request
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import ptax

CD_CVM = "9512"  # Petroleo Brasileiro S.A. - Petrobras
URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/{doc}/DADOS/{doc_l}_cia_aberta_{ano}.zip"
FONTE = "CVM Dados Abertos (ITR/DFP consolidado), convertido pela PTAX do Banco Central"

_RE_DEMO = re.compile(r"_(DRE|BPA|BPP|DFC_MI|DFC_MD)_con_")


# ---------------------------------------------------------------------------
# Leitura dos arquivos da CVM
# ---------------------------------------------------------------------------
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def baixa(doc: str, ano: int) -> bytes:  # pragma: no cover - rede
    url = URL.format(doc=doc, doc_l=doc.lower(), ano=ano)
    pedido = urllib.request.Request(url, headers={"User-Agent": "oil-gas-financial-dashboard"})
    with urllib.request.urlopen(pedido, timeout=180) as resposta:
        return resposta.read()


def linhas(zbytes: bytes, cd_cvm: str = CD_CVM) -> list[dict[str, Any]]:
    """Linhas consolidadas da companhia em todos os CSVs do zip, em R$ milhoes."""
    lidas = []
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        for nome in z.namelist():
            achado = _RE_DEMO.search(nome)
            if not achado:
                continue
            demo = achado.group(1).replace("_MD", "_MI")
            with z.open(nome) as f:
                leitor = csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";")
                for r in leitor:
                    if r.get("CD_CVM", "").lstrip("0") != cd_cvm:
                        continue
                    if _norm(r.get("ORDEM_EXERC", "")) != "ultimo":
                        continue
                    escala = 1000 if r.get("ESCALA_MOEDA", "").upper().startswith("MIL") else 1
                    lidas.append({
                        "demo": demo,
                        "versao": int(r.get("VERSAO") or 1),
                        "ini": r.get("DT_INI_EXERC", ""),
                        "fim": r["DT_FIM_EXERC"],
                        "conta": r["CD_CONTA"],
                        "desc": _norm(r["DS_CONTA"]),
                        "valor": float(r["VL_CONTA"]) * escala / 1e6,
                    })
    # Reapresentacao: vale a versao mais alta de cada (demonstracao, conta, periodo).
    melhor: dict[tuple, dict[str, Any]] = {}
    for item in lidas:
        chave = (item["demo"], item["conta"], item["ini"], item["fim"])
        if chave not in melhor or item["versao"] > melhor[chave]["versao"]:
            melhor[chave] = item
    return list(melhor.values())


def _fim(p: str) -> str:
    return ptax.fim_do_trimestre(p).isoformat()


def _ini(p: str) -> str:
    ano, q = int(p[:4]), int(p[-1])
    return f"{ano}-{3 * q - 2:02d}-01"


def anterior(p: str) -> str:
    ano, q = int(p[:4]), int(p[-1])
    return f"{ano - 1}-Q4" if q == 1 else f"{ano}-Q{q - 1}"


def _busca(ls, demo, fim, ini=None, conta=None, desc=None, nivel=None, prefixo=None):
    """Soma das contas que casam (codigo exato ou regex na descricao).

    Quando uma conta e uma subconta casam com a mesma descricao, so as folhas
    entram -- do contrario o valor seria contado duas vezes.
    """
    sel = []
    for item in ls:
        if item["demo"] != demo or item["fim"] != fim:
            continue
        if ini is not None and item["ini"] != ini:
            continue
        if conta and item["conta"] != conta:
            continue
        if desc and not re.search(desc, item["desc"]):
            continue
        if nivel is not None and item["conta"].count(".") != nivel:
            continue
        if prefixo and not item["conta"].startswith(prefixo):
            continue
        sel.append(item)
    codigos = {item["conta"] for item in sel}
    folhas = [
        item for item in sel
        if not any(c != item["conta"] and c.startswith(item["conta"] + ".") for c in codigos)
    ]
    return sum(item["valor"] for item in folhas) if folhas else None


def fluxo(ls, demo, p, **kw):
    """Valor do trimestre isolado; se so houver acumulado, diferenca de acumulados."""
    v = _busca(ls, demo, _fim(p), ini=_ini(p), **kw)
    if v is not None:
        return v
    ano, q = p[:4], int(p[-1])
    acumulado = _busca(ls, demo, _fim(p), ini=f"{ano}-01-01", **kw)
    if acumulado is None or q == 1:
        return acumulado
    ate_o_anterior = _busca(ls, demo, _fim(f"{ano}-Q{q - 1}"), ini=f"{ano}-01-01", **kw)
    return None if ate_o_anterior is None else acumulado - ate_o_anterior


def saldo(ls, p, **kw):
    v = None
    for demo in ("BPA", "BPP"):
        x = _busca(ls, demo, _fim(p), **kw)
        if x is not None:
            v = (v or 0) + x
    return v


def trimestre_brl(ls, p: str) -> dict[str, float | None]:
    """Um trimestre em R$ milhoes, nas definicoes do cabecalho deste arquivo."""
    r: dict[str, float | None] = {
        "receita": fluxo(ls, "DRE", p, conta="3.01"),
        "lucro_liquido": fluxo(ls, "DRE", p, conta="3.11.01"),
        "lair": fluxo(ls, "DRE", p, conta="3.07"),
        "resultado_financeiro": fluxo(ls, "DRE", p, conta="3.06"),
        "depreciacao": fluxo(ls, "DFC_MI", p, desc=r"^deprecia.*(deplec|amortiz)", nivel=3),
        "fco": fluxo(ls, "DFC_MI", p, conta="6.01"),
        "capex": fluxo(ls, "DFC_MI", p, desc=r"aquisi.*(imobilizado|intang)", nivel=2),
        "dividendos": fluxo(
            ls, "DFC_MI", p, nivel=2, prefixo="6.03",
            desc=r"^(?!.*nao controlador)(dividendos|juros sobre (o )?capital proprio).*pag",
        ),
        "recompras": fluxo(
            ls, "DFC_MI", p, nivel=2, prefixo="6.03",
            desc=r"recompra de acoes|aquisicao de acoes (proprias|em tesouraria)",
        ),
        "patrimonio": _busca(ls, "BPP", _fim(p), conta="2.03"),
        "ativos": _busca(ls, "BPA", _fim(p), conta="1"),
    }
    if r["capex"] is not None:
        r["capex"] = abs(r["capex"])
    for campo in ("dividendos", "recompras"):
        if r[campo] is not None:
            r[campo] = abs(r[campo])
    # DFC lida (ha dividendos) e nenhuma linha de recompra: nao houve recompra.
    if r["recompras"] is None and r["dividendos"] is not None:
        r["recompras"] = 0.0
    r["ebitda"] = None
    if None not in (r["lair"], r["resultado_financeiro"], r["depreciacao"]):
        r["ebitda"] = r["lair"] - r["resultado_financeiro"] + r["depreciacao"]

    financiamentos = saldo(ls, p, desc=r"^(emprestimos e )?financiamentos$")
    arrendamentos = saldo(ls, p, desc=r"arrendamento")
    caixa = saldo(ls, p, conta="1.01.01")
    titulos = saldo(ls, p, desc=r"^(titulos|aplicacoes financeiras)", nivel=2, prefixo="1.01.")
    titulos_lp = _busca(ls, "BPA", _fim(p), desc=r"^aplicacoes financeiras", nivel=3, prefixo="1.02.01.")
    r["divida_total"] = None
    r["caixa"] = None
    if None not in (financiamentos, arrendamentos, caixa):
        r["divida_total"] = financiamentos + arrendamentos
        r["caixa"] = caixa + (titulos or 0) + (titulos_lp or 0)
    return r


# ---------------------------------------------------------------------------
# Conversao para US$ e formato do pipeline
# ---------------------------------------------------------------------------
FLUXOS = ("receita", "lucro_liquido", "ebitda", "fco", "capex", "dividendos", "recompras")
ESTOQUES = ("divida_total", "caixa", "patrimonio", "ativos")


def converte(brl: dict[str, float | None], taxas: dict[str, Any]) -> dict[str, float | None]:
    """R$ milhoes -> US$ milhoes. Fluxo pela media, estoque pelo fechamento."""
    usd: dict[str, float | None] = {}
    for campo in FLUXOS:
        usd[campo] = None if brl.get(campo) is None else brl[campo] / taxas["media"]
    for campo in ESTOQUES:
        usd[campo] = None if brl.get(campo) is None else brl[campo] / taxas["fechamento"]
    return usd


def ultimo_periodo(ls) -> str | None:
    """Trimestre mais recente com DRE entregue."""
    fins = sorted({item["fim"] for item in ls if item["demo"] == "DRE" and item["conta"] == "3.01"})
    if not fins:
        return None
    fim = date.fromisoformat(fins[-1])
    return f"{fim.year}-Q{(fim.month - 1) // 3 + 1}"


def monta_bruto(ls, periodo: str | None = None, cotacoes=None) -> dict[str, Any] | None:
    """Devolve o trimestre no formato que `update_fundamentals.aplica_fundamentos` espera.

    Levanta `ptax.PtaxIncompleta` se nao houver PTAX completa para o trimestre:
    sem a taxa certa nao ha conversao, e sem conversao nao ha promocao.
    """
    periodo = periodo or ultimo_periodo(ls)
    if periodo is None:
        return None
    brl = trimestre_brl(ls, periodo)
    if brl["receita"] is None or brl["lucro_liquido"] is None:
        return None
    taxas = ptax.taxas(periodo, cotacoes)
    usd = converte(brl, taxas)

    # Lucro de 12 meses para ROE/ROA: cada trimestre pela SUA media. Converter a
    # soma em reais por uma taxa so misturaria quatro cambios num.
    ttm: dict[str, float] = {}
    anteriores = []
    soma, p = usd["lucro_liquido"], periodo
    completos = 1
    for _ in range(4):
        p = anterior(p)
        brl_ant = trimestre_brl(ls, p)
        if brl_ant["receita"] is None or brl_ant["lucro_liquido"] is None:
            break
        try:
            usd_ant = converte(brl_ant, ptax.taxas(p, cotacoes))
        except ptax.PtaxIncompleta:
            break
        if completos < 4:
            soma += usd_ant["lucro_liquido"]
            completos += 1
        anteriores.append({"fim": ptax.fim_do_trimestre(p), "linhas": usd_ant, "ttm": {}})
    if completos == 4:
        ttm["lucro_liquido"] = soma

    return {
        "fim": ptax.fim_do_trimestre(periodo),
        "linhas": usd,
        "ttm": ttm,
        "anteriores": anteriores,
        "moeda": "USD",
        "fonte": FONTE,
        "conversao": {
            "moeda_origem": "BRL",
            "ptax_media": taxas["media"],
            "ptax_fechamento": taxas["fechamento"],
            "data_fechamento": taxas["data_fechamento"],
            "regra": "fluxos pela media do trimestre; saldos pelo fechamento do ultimo dia util",
            "receita_brl": round(brl["receita"]),
            "lucro_liquido_brl": round(brl["lucro_liquido"]),
        },
    }


def coleta(hoje: date | None = None) -> dict[str, Any] | None:  # pragma: no cover - rede
    """Baixa ITR do ano e do anterior e a DFP do anterior, e monta o ultimo trimestre."""
    hoje = hoje or date.today()
    ls: list[dict[str, Any]] = []
    for doc, ano in (("ITR", hoje.year), ("ITR", hoje.year - 1), ("DFP", hoje.year - 1)):
        try:
            ls += linhas(baixa(doc, ano))
        except Exception as exc:
            print(f"  ! CVM: {doc} {ano} indisponivel ({exc.__class__.__name__}: {exc})")
    return monta_bruto(ls) if ls else None


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--periodo", help="AAAA-QN; padrao: o mais recente entregue")
    parser.add_argument("--zip", nargs="*", type=Path, help="zips ITR/DFP locais em vez de baixar")
    args = parser.parse_args(argv)
    if args.zip:
        ls: list[dict[str, Any]] = []
        for z in args.zip:
            ls += linhas(z.read_bytes())
        bruto = monta_bruto(ls, args.periodo)
    elif args.periodo:
        ano = int(args.periodo[:4])
        ls = []
        for doc, a in (("ITR", ano), ("ITR", ano - 1), ("DFP", ano - 1)):
            ls += linhas(baixa(doc, a))
        bruto = monta_bruto(ls, args.periodo)
    else:
        bruto = coleta()
    if bruto is None:
        print("CVM: nenhum trimestre da Petrobras encontrado.")
        return 1
    print(json.dumps(bruto, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
