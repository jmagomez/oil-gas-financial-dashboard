import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("cd", Path(__file__).resolve().parent.parent / "poc" / "confere_documentos.py")
cd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cd)

HTML = b"<table><tr><td>Revenue</td><td>65,406</td></tr><tr><td>Debt</td><td>1 075</td></tr><tr><td>X</td><td>123,4567</td></tr></table>"


def plano(*checks):
    return {"documentos": [{"url": "u", "checagens": [dict(periodo="2025-Q2", campo=c, valor=v, **kw) for c, v, kw in checks]}]}


def test_formatos_e_fronteira():
    t = cd.texto(HTML)
    assert cd.presente(65406, t) and cd.presente(1075, t) and cd.presente(-1075, t)
    assert not cd.presente(4567, t)  # não casa dentro de 123,4567
    assert not cd.presente(65407, t)


def test_derivado_e_falha():
    p = plano(("SHEL:a", 65406, {}), ("SHEL:b", 1075, {}), ("SHEL:soma", 66481, {"derivado": ["SHEL:a", "SHEL:b"]}),
              ("SHEL:errado", 999, {}))
    falhas, cont = cd.confere(p, lambda u: HTML)
    assert cont["SHEL"] == {"checagens": 4, "no_texto": 2, "derivadas_ok": 1}
    assert len(falhas) == 1 and "SHEL:errado" in falhas[0]


def test_plano_do_repositorio_coerente():
    import json
    p = json.loads(cd.PLANO.read_text(encoding="utf-8"))
    n = sum(len(d["checagens"]) for d in p["documentos"])
    assert n == 260 and all(d["url"].startswith("https://") for d in p["documentos"])


def test_plano_bate_com_a_coleta():
    """Cada valor do plano é o mesmo gravado em poc/coleta/<TICKER>.json (o plano não pode divergir da série)."""
    import json
    p = json.loads(cd.PLANO.read_text(encoding="utf-8"))
    base = cd.RAIZ / "poc" / "coleta"
    dif = []
    for d in p["documentos"]:
        for c in d["checagens"]:
            t, campo = c["campo"].split(":", 1)
            q = json.loads((base / f"{t}.json").read_text(encoding="utf-8"))["trimestres"].get(c["periodo"])
            if q is None:
                continue  # comparativo de um trimestre fora da série gravada
            if campo.startswith(("eb.", "dl.")):
                grupo = q.get("ebitda_componentes" if campo.startswith("eb.") else "divida_componentes", {})
                v = grupo.get(campo[3:])
            else:
                v = q.get(campo)
            if v is not None and abs(abs(v) - abs(c["valor"])) > 0.5:
                dif.append((t, c["periodo"], campo, v, c["valor"]))
    assert not dif, dif
