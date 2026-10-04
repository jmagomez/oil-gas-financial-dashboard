"""Coleta automática pela API XBRL da SEC (poc/coleta_sec_xbrl.py), sem rede (fixtures reais)."""
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("xbrl", ROOT / "poc" / "coleta_sec_xbrl.py")
xb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xb)


def _calc(t):
    linhas = xb.coleta(t, offline=True)
    return {p: xb.trimestre(t, linhas, p) for p in xb.periodos("2026-Q2")}


def test_xbrl_reproduz_a_coleta_dos_releases():
    # conferência independente: os números lidos dos releases batem com os 10-Q/10-K em XBRL
    for t in ("XOM", "CVX"):
        assert xb.compara(t, _calc(t)) == [], t


def test_quarto_trimestre_sai_do_ano_menos_nove_meses():
    v = _calc("XOM")["2025-Q4"]
    assert v["componentes"]["lair"] == 41268 - 33237
    assert v["origem"]["fluxo_caixa_operacional"].startswith("acumulado 12m")


def test_reorganizacao_da_exxonmobil_junta_os_dois_ciks():
    v = _calc("XOM")["2026-Q2"]
    assert v["divida_liquida"] == 10139 + 32229 - 10588
    assert v["fluxo_caixa_operacional"] == 32260 - 8705


def test_caixa_da_chevron_exclui_caixa_restrito():
    v = _calc("CVX")["2026-Q2"]
    assert v["componentes"]["caixa"] == 9582 - 236 - 819


def test_receita_da_exxonmobil_fica_fora_por_falta_de_conceito_sem_dimensao():
    assert _calc("XOM")["2025-Q2"]["receita"] is None


def test_linhas_de_companyfacts_fica_com_o_arquivamento_mais_recente():
    cf = {"facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": [
        {"start": "2025-01-01", "end": "2025-03-31", "val": 1e9, "filed": "2025-05-01", "form": "10-Q"},
        {"start": "2025-01-01", "end": "2025-03-31", "val": 2e9, "filed": "2026-05-01", "form": "10-Q"}]}}}}}
    l = xb.linhas_de_companyfacts(cf, {"NetIncomeLoss"})
    assert len(l) == 1 and l[0]["valor"] == 2000
