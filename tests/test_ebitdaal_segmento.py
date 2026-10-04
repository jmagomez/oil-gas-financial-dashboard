"""EBITDAaL e EBITDA do upstream por boe (poc/decomposicao.json → poc/build_poc.py)."""
import importlib.util
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
D = json.loads((RAIZ / "poc" / "decomposicao.json").read_text(encoding="utf-8"))
_spec = importlib.util.spec_from_file_location("build_poc_ebitdaal", RAIZ / "poc" / "build_poc.py")
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)
_dados, _empresas, _base = bp.carrega()
FATO = bp.calcula(_empresas, _base, bp.aplica_regras(_dados, _empresas, _base))


def fato(e, p, i):
    return next((f for f in FATO if f["empresa"] == e and f["periodo"] == p and f["indicador"] == i), None)


def test_somas_anuais_do_release_da_petrobras():
    # o release traz o total de 2025: arrendamentos 52.437 e EBITDA do E&P 219.715 (R$ mi)
    anos = ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"]
    assert sum(D["pagamentos_arrendamento"]["PBR"]["valores_brl"][p] for p in anos) == 52437
    assert sum(D["segmento_upstream"]["PBR"]["ebitda_brl"][p] for p in anos) == 219715


def test_componentes_somam_ao_ebitda_do_segmento():
    x = D["segmento_upstream"]["XOM"]
    for p, v in x["ebitda"].items():
        c = x["componentes"]
        assert c["lucro_antes_ir"][p] + c["juros"][p] + c["dda_incl_impairment"][p] == v
    e = D["segmento_upstream"]["EQNR"]
    for p, v in e["ebitda"].items():
        assert e["componentes"]["adjusted_operating_income_ep"][p] + e["componentes"]["adjusted_dda_ep"][p] == v


def test_ebitdaal_menor_ou_igual_ao_ebitda_e_ressalva_quando_rateado():
    for e, pag in D["pagamentos_arrendamento"].items():
        for p in pag["valores"]:
            m, mal = fato(e, p, "margem_ebitda"), fato(e, p, "margem_ebitdaal")
            assert mal is not None and mal["valor"] <= m["valor"] + 1e-9
            if pag.get("ressalva"):
                assert mal["status"] != "verde"


def test_upstream_por_boe_usa_producao_do_segmento_quando_existe():
    sh = D["segmento_upstream"]["SHEL"]
    f = fato("SHEL", "2026-Q2", "ebitda_upstream_boe")
    assert abs(f["valor"] - sh["ebitda"]["2026-Q2"] * 1000 / (sh["producao_kboed"]["2026-Q2"] * 91)) < 0.06
    assert fato("TTE", "2026-Q2", "ebitda_upstream_boe") is None  # lacuna documentada
