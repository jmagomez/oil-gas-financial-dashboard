#!/usr/bin/env python3
"""Conferência determinística dos números coletados contra o texto do documento oficial.

Para Shell, BP, Equinor e TotalEnergies (6-K e releases, sem XBRL trimestral), cada valor de
poc/coleta/<TICKER>.json listado em poc/conferencia/plano_documentos.json precisa aparecer no
texto do documento de origem. HTML: texto das células; PDF: pdfminer.six. O número é procurado
como 12,345 / 12.345 / 12 345 (sem casar dentro de outro número). Valores que o documento não
imprime (somas calculadas na coleta) são marcados como "derivado" e conferidos pela soma dos
componentes. Não usa modelo de linguagem.

Uso:
    python3 poc/confere_documentos.py                 # baixa os documentos e confere
    python3 poc/confere_documentos.py --cache DIR     # usa/guarda cópias locais (url → arquivo)
Saída 1 se algum valor não for encontrado.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLANO = RAIZ / "poc" / "conferencia" / "plano_documentos.json"
UA = "oil-gas-financial-dashboard 60618813+jmagomez@users.noreply.github.com"  # a SEC exige nome e e-mail de contato (sem isso: HTTP 403)


def baixa(url: str, cache: Path | None) -> bytes:
    if cache:
        f = cache / hashlib.sha1(url.encode()).hexdigest()
        if f.exists():
            return f.read_bytes()
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120) as r:
        b = r.read()
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b)
    return b


def texto(b: bytes) -> str:
    if b[:5] == b"%PDF-":
        from pdfminer.high_level import extract_text  # pip install pdfminer.six
        return extract_text(io.BytesIO(b))
    h = b.decode("utf-8", "ignore")
    h = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", h)
    h = re.sub(r"(?i)</(td|th|p|div|tr|li)>", " | ", h)
    return html.unescape(re.sub(r"<[^>]+>", " ", h)).replace("\xa0", " ")


def variantes(v: float) -> list[str]:
    a = round(abs(v))
    if a < 1000:
        return [str(a)]
    en = f"{a:,}"
    return [en, en.replace(",", "."), en.replace(",", " ")]


def presente(v: float, t: str) -> bool:
    return any(re.search(r"(^|[^0-9.,])" + re.escape(x) + r"($|[^0-9])", t) for x in variantes(v))


def confere(plano: dict, obter) -> tuple[list[str], dict]:
    falhas, cont = [], {}
    for doc in plano["documentos"]:
        try:
            t = texto(obter(doc["url"]))
        except Exception as e:  # rede, PDF corrompido
            falhas.append(f"ERRO ao ler {doc['url']}: {e}")
            continue
        vals = {(c["periodo"], c["campo"]): c["valor"] for c in doc["checagens"]}
        for c in doc["checagens"]:
            emp = c["campo"].split(":")[0]
            k = cont.setdefault(emp, {"checagens": 0, "no_texto": 0, "derivadas_ok": 0})
            k["checagens"] += 1
            if presente(c["valor"], t):
                k["no_texto"] += 1
            elif c.get("derivado") and all((c["periodo"], x) in vals for x in c["derivado"]) and \
                    abs(sum(abs(vals[(c["periodo"], x)]) for x in c["derivado"]) - abs(c["valor"])) <= 1:
                k["derivadas_ok"] += 1
            else:
                falhas.append(f"{c['periodo']} {c['campo']} = {c['valor']:,} não encontrado em {doc['url']}")
    return falhas, cont


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plano", default=str(PLANO))
    ap.add_argument("--cache")
    a = ap.parse_args(argv)
    plano = json.loads(Path(a.plano).read_text(encoding="utf-8"))
    cache = Path(a.cache) if a.cache else None
    falhas, cont = confere(plano, lambda u: baixa(u, cache))
    for e, k in sorted(cont.items()):
        print(f"{e}: {k['no_texto']} no texto + {k['derivadas_ok']} derivadas de {k['checagens']}")
    print("\n".join(falhas) or "Todos os valores conferem com os documentos oficiais")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
