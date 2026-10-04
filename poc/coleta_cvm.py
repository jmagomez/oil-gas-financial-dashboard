#!/usr/bin/env python3
"""Coleta automática dos trimestres da Petrobras pelo Portal de Dados Abertos da CVM (ITR/DFP).

Fonte: https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/{ITR,DFP}/DADOS/{itr,dfp}_cia_aberta_AAAA.zip
(demonstrações consolidadas entregues pela própria companhia). Não usa agregador.

Campos em R$ milhões (a conversão para US$ fica em poc/integra_fontes_primarias.py, pela PTAX):
    receita_brl          3.01  Receita de venda de bens e/ou serviços
    lucro_liquido_brl    3.11.01  Lucro atribuído a sócios da controladora
    lair_brl             3.07  Resultado antes dos tributos sobre o lucro
    resultado_financeiro_brl  3.06
    da_brl               DFC: depreciação, depleção e amortização (6.01.01.xx)
    ebitda_brl           = lair − resultado financeiro + D&A  (RCVM 156; no 1T25: 53.635 − 10.595 + 18.976 = 62.016)
    fco_brl              6.01
    capex_brl            DFC: aquisições de ativos imobilizados e intangíveis (6.02.xx), positivo
    divida_bruta_brl     financiamentos (2.01.04 + 2.02.01) + arrendamentos (circulante e não circulante)
    divida_liquida_brl   = dívida bruta − caixa e equivalentes − aplicações financeiras de curto e longo prazo
                         (disponibilidades ajustadas, como a Petrobras define)

Trimestres: a DRE do ITR traz o trimestre isolado; a DFC só o acumulado (diferença de acumulados);
o 4T sai da DFP (ano − 9 meses).

Uso:
    python3 poc/coleta_cvm.py --verificar     # baixa ITR/DFP e compara com poc/coleta/PBR.json
    python3 poc/coleta_cvm.py --zip arquivo.zip ...  # usa zips locais
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import unicodedata
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
COLETA = RAIZ / "poc" / "coleta"
CD_CVM = "9512"  # Petróleo Brasileiro S.A. - Petrobras
URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/{doc}/DADOS/{doc_l}_cia_aberta_{ano}.zip"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def baixa(doc: str, ano: int) -> bytes:
    url = URL.format(doc=doc, doc_l=doc.lower(), ano=ano)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "oil-gas-financial-dashboard"}),
                                timeout=180) as r:
        return r.read()


def linhas(zbytes: bytes, cd_cvm: str = CD_CVM) -> list[dict]:
    """Linhas consolidadas da companhia em todos os CSVs do zip (DRE, BPA, BPP, DFC_MI)."""
    out = []
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        for nome in z.namelist():
            if not re.search(r"_(DRE|BPA|BPP|DFC_MI|DFC_MD)_con_", nome):
                continue
            demo = re.search(r"_(DRE|BPA|BPP|DFC_MI|DFC_MD)_con_", nome).group(1)
            with z.open(nome) as f:
                for r in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";"):
                    if r.get("CD_CVM", "").lstrip("0") != cd_cvm or _norm(r.get("ORDEM_EXERC", "")) != "ultimo":
                        continue
                    esc = 1000 if r.get("ESCALA_MOEDA", "").upper().startswith("MIL") else 1
                    out.append(dict(demo=demo.replace("_MD", "_MI"), versao=int(r.get("VERSAO") or 1),
                                    ini=r.get("DT_INI_EXERC", ""), fim=r["DT_FIM_EXERC"], conta=r["CD_CONTA"],
                                    desc=_norm(r["DS_CONTA"]), valor=float(r["VL_CONTA"]) * esc / 1e6))
    # reapresentações: fica a versão mais alta de cada (demonstração, conta, período)
    melhor = {}
    for l in out:
        k = (l["demo"], l["conta"], l["ini"], l["fim"])
        if k not in melhor or l["versao"] > melhor[k]["versao"]:
            melhor[k] = l
    return list(melhor.values())


def _fim(p):
    a, q = int(p[:4]), int(p[-1])
    return {1: f"{a}-03-31", 2: f"{a}-06-30", 3: f"{a}-09-30", 4: f"{a}-12-31"}[q]


def _ini(p):
    a, q = int(p[:4]), int(p[-1])
    return f"{a}-{3 * q - 2:02d}-01"


def _busca(ls, demo, fim, ini=None, conta=None, desc=None, nivel=None, prefixo=None):
    """Soma das contas que casam (conta exata ou regex na descrição; nivel = nº de pontos do código).

    Quando uma conta e uma subconta casam com a mesma descrição, só as folhas entram (sem dupla contagem)."""
    sel = []
    for l in ls:
        if l["demo"] != demo or l["fim"] != fim or (ini is not None and l["ini"] != ini):
            continue
        if conta and l["conta"] != conta:
            continue
        if desc and not re.search(desc, l["desc"]):
            continue
        if nivel is not None and l["conta"].count(".") != nivel:
            continue
        if prefixo and not l["conta"].startswith(prefixo):
            continue
        sel.append(l)
    codigos = {l["conta"] for l in sel}
    sel = [l for l in sel if not any(c != l["conta"] and c.startswith(l["conta"] + ".") for c in codigos)]
    return sum(l["valor"] for l in sel) if sel else None


def fluxo(ls, demo, p, **kw):
    """Trimestre isolado; se só houver acumulado, diferença de acumulados."""
    v = _busca(ls, demo, _fim(p), ini=_ini(p), **kw)
    if v is not None:
        return v
    a, q = p[:4], int(p[-1])
    ytd = _busca(ls, demo, _fim(p), ini=f"{a}-01-01", **kw)
    if ytd is None or q == 1:
        return ytd
    ant = _busca(ls, demo, _fim(f"{a}-Q{q - 1}"), ini=f"{a}-01-01", **kw)
    return None if ant is None else ytd - ant


def saldo(ls, p, **kw):
    v = None
    for demo in ("BPA", "BPP"):
        x = _busca(ls, demo, _fim(p), **kw)
        if x is not None:
            v = (v or 0) + x
    return v


def trimestre(ls, p) -> dict:
    r = dict(
        receita_brl=fluxo(ls, "DRE", p, conta="3.01"),
        lucro_liquido_brl=fluxo(ls, "DRE", p, conta="3.11.01"),
        lair_brl=fluxo(ls, "DRE", p, conta="3.07"),
        resultado_financeiro_brl=fluxo(ls, "DRE", p, conta="3.06"),
        da_brl=fluxo(ls, "DFC_MI", p, desc=r"^deprecia.*(deplec|amortiz)", nivel=3),
        fco_brl=fluxo(ls, "DFC_MI", p, conta="6.01"),
        capex_brl=fluxo(ls, "DFC_MI", p, desc=r"aquisi.*(imobilizado|intang)", nivel=2),
    )
    if r["capex_brl"] is not None:
        r["capex_brl"] = abs(r["capex_brl"])
    if None not in (r["lair_brl"], r["resultado_financeiro_brl"], r["da_brl"]):
        r["ebitda_brl"] = r["lair_brl"] - r["resultado_financeiro_brl"] + r["da_brl"]
    financ = saldo(ls, p, desc=r"^(emprestimos e )?financiamentos$")
    arrend = saldo(ls, p, desc=r"arrendamento")
    caixa = saldo(ls, p, conta="1.01.01")
    titulos = saldo(ls, p, desc=r"^(titulos|aplicacoes financeiras)", nivel=2, prefixo="1.01.")
    # Disponibilidades ajustadas da Petrobras incluem os títulos de longo prazo (1.02.01.x): no 1T25,
    # R$ 4.806 mi ao custo amortizado; sem eles a dívida líquida saía 1,4% acima da divulgada.
    titulos_lp = _busca(ls, "BPA", _fim(p), desc=r"^aplicacoes financeiras", nivel=3, prefixo="1.02.01.")
    if titulos_lp:
        titulos = (titulos or 0) + titulos_lp
    r.update(financiamentos_brl=financ, arrendamentos_brl=arrend, caixa_brl=caixa, titulos_brl=titulos)
    if None not in (financ, arrend, caixa):
        r["divida_liquida_brl"] = financ + arrend - caixa - (titulos or 0)
    return {k: (round(v) if isinstance(v, float) else v) for k, v in r.items()}


CAMPOS = ["receita_brl", "lucro_liquido_brl", "ebitda_brl", "lair_brl", "resultado_financeiro_brl", "da_brl",
          "fco_brl", "capex_brl", "divida_liquida_brl"]


def compara(calc: dict, tolerancia=0.005) -> list[str]:
    ref = json.loads((COLETA / "PBR.json").read_text(encoding="utf-8"))["trimestres"]
    out = []
    for p, v in calc.items():
        for c in CAMPOS:
            a, b = v.get(c), (ref.get(p) or {}).get(c)
            if a is None or b is None:
                out.append(f"PBR {p} {c}: CVM {a} / release {b} (ausente)") if b is not None else None
                continue
            if abs(a - b) > max(2, tolerancia * abs(b)):
                out.append(f"PBR {p} {c}: CVM {a:,} vs release {b:,}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--anos", default="2025,2026")
    ap.add_argument("--ate", default="2026-Q2")
    ap.add_argument("--zip", nargs="*", help="zips ITR/DFP locais em vez de baixar")
    ap.add_argument("--verificar", action="store_true")
    ap.add_argument("--gravar", action="store_true", help="grava poc/coleta/PBR_cvm.json")
    a = ap.parse_args(argv)
    ls = []
    if a.zip:
        for z in a.zip:
            ls += linhas(Path(z).read_bytes())
    else:
        for ano in map(int, a.anos.split(",")):
            for doc in ("ITR", "DFP"):
                try:
                    ls += linhas(baixa(doc, ano))
                except Exception as e:  # DFP do ano corrente ainda não existe
                    print(f"aviso: {doc} {ano} indisponível ({e})")
    ps, ano, q = [], 2025, 1
    while f"{ano}-Q{q}" <= a.ate:
        ps.append(f"{ano}-Q{q}")
        ano, q = (ano + 1, 1) if q == 4 else (ano, q + 1)
    calc = {p: trimestre(ls, p) for p in ps}
    for p, v in calc.items():
        print("PBR", p, json.dumps(v, ensure_ascii=False))
    falhas = compara(calc) if a.verificar else []
    if a.verificar:
        print("\n".join(falhas) or "CVM confere com a coleta dos releases (tolerância 0,5%)")
    if a.gravar:
        (COLETA / "PBR_cvm.json").write_text(json.dumps(dict(empresa="PBR", fonte="CVM Dados Abertos (ITR/DFP)",
                                                             trimestres=calc), ensure_ascii=False, indent=1) + "\n",
                                             encoding="utf-8")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
