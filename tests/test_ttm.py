"""Testes da base de 12 meses (TTM) dos indicadores do trimestre.

Por que existe: anualizar UM trimestre x4 extrapola aquele trimestre para o ano
inteiro. Num setor cujo resultado acompanha o preco da commodity, isso distorce
muito. Medido nos dados reais do 2T26 (trimestre de pico): FCF yield x4
superestimava entre 54% e 176%; ND/EBITDA x4 subestimava a alavancagem entre
8% e 40%.

O snapshot congelado tem historico vazio -- de proposito, ele retrata a base
antes do backfill. Por isso estes testes montam a janela inline: sem isso a
camada TTM ficaria sem cobertura e a suite passaria verde sem exercita-la.
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import build_dashboard as bd  # noqa: E402


def _tri(periodo, receita=100, ebitda=40, fcf=10, capex=-20, prod=1000):
    return {
        "periodo": periodo, "receita": receita, "lucro_liquido": receita * 0.1,
        "ebitda": ebitda, "fluxo_caixa_operacional": fcf - capex, "fcf": fcf,
        "capex": capex, "divida_liquida": 500, "producao_kboed": prod,
    }


def _empresa(historico, q_ebitda=40, q_fcf=10, nd=500, market_cap=1000):
    q = dict(_tri("Q2 2026", ebitda=q_ebitda, fcf=q_fcf), trimestre="Q2 2026")
    q.pop("periodo")
    q["divida_liquida"] = nd
    return {
        "ticker": "TST", "nome": "Teste", "pais": "X",
        "fy2025": dict(_tri("FY2025", receita=400, ebitda=160, fcf=40, capex=-80)),
        "q_recente": q,
        "mercado": {"market_cap": market_cap, "pe": 10.0, "ev_ebitda": 5.0,
                    "dividend_yield_pct": 2.0, "preco_acao": 20.0},
        "historico": historico,
        "fontes": ["x"],
    }


# ---------------------------------------------------------------------------
# Calculo do TTM
# ---------------------------------------------------------------------------
def test_ttm_soma_os_quatro_ultimos_trimestres():
    hist = [_tri("2025-Q2", ebitda=10), _tri("2025-Q3", ebitda=20),
            _tri("2025-Q4", ebitda=30), _tri("2026-Q1", ebitda=40)]
    ttm = bd.calcular_ttm(_empresa(hist, q_ebitda=50))
    # janela = 3 ultimos do historico + q_recente = 20+30+40+50
    assert ttm["ebitda"] == 140
    assert ttm["janela"] == ["2025-Q3", "2025-Q4", "2026-Q1", "Q2 2026"]


def test_producao_e_media_e_nao_soma():
    """Producao e taxa por dia. Somar 4 trimestres daria 4x a producao real."""
    hist = [_tri("2025-Q2", prod=1000), _tri("2025-Q3", prod=1000),
            _tri("2025-Q4", prod=1000), _tri("2026-Q1", prod=1000)]
    ttm = bd.calcular_ttm(_empresa(hist))
    assert ttm["producao_kboed"] == 1000


def test_estoque_nao_entra_no_ttm():
    """Somar saldo de balanco (divida liquida) ao longo de 4 trimestres nao
    significa nada. So fluxo acumula."""
    assert "divida_liquida" not in bd.CAMPOS_FLUXO_TTM
    assert "divida_patrimonio_pct" not in bd.CAMPOS_FLUXO_TTM


def test_janela_incompleta_devolve_none_em_vez_de_estimar():
    assert bd.calcular_ttm(_empresa([_tri("2026-Q1")])) is None
    assert bd.calcular_ttm(_empresa([])) is None


def test_trimestre_com_campo_nulo_nao_vira_soma_parcial():
    """Faltando um numero, o campo sai None -- nao a soma dos que existem."""
    hist = [_tri("2025-Q2"), _tri("2025-Q3"), _tri("2025-Q4"), _tri("2026-Q1")]
    hist[1]["ebitda"] = None
    ttm = bd.calcular_ttm(_empresa(hist))
    assert ttm["ebitda"] is None
    assert ttm["receita"] is not None  # os outros campos seguem validos


# ---------------------------------------------------------------------------
# Efeito nos indicadores
# ---------------------------------------------------------------------------
def test_nd_ebitda_do_trimestre_usa_ttm_quando_disponivel():
    hist = [_tri("2025-Q2", ebitda=10), _tri("2025-Q3", ebitda=10),
            _tri("2025-Q4", ebitda=10), _tri("2026-Q1", ebitda=10)]
    e = _empresa(hist, q_ebitda=100, nd=600)   # trimestre de pico
    d = bd.enriquecer({"empresas": [e]})["empresas"][0]["q_recente"]["derivados"]
    # TTM = 10+10+10+100 = 130 -> 600/130 = 4.62
    # x4 daria 600/400 = 1.50, subestimando a alavancagem em 3x
    assert d["base_12m_ebitda"] == "ttm"
    assert d["nd_ebitda_x"] == pytest.approx(600 / 130, abs=0.01)


def test_fcf_yield_do_trimestre_usa_ttm_quando_disponivel():
    hist = [_tri("2025-Q2", fcf=5), _tri("2025-Q3", fcf=5),
            _tri("2025-Q4", fcf=5), _tri("2026-Q1", fcf=5)]
    e = _empresa(hist, q_fcf=50, market_cap=1000)
    d = bd.enriquecer({"empresas": [e]})["empresas"][0]["q_recente"]["derivados"]
    # TTM = 5+5+5+50 = 65 -> 6,5%. x4 daria 20%, tres vezes maior.
    assert d["fcf_yield_pct"] == pytest.approx(6.5, abs=0.01)


def test_sem_historico_cai_para_x4_e_avisa_qual_base_usou():
    """Fallback explicito: o numero sai, mas o payload diz que base o gerou."""
    d = bd.enriquecer({"empresas": [_empresa([], q_ebitda=100, nd=600)]})
    dv = d["empresas"][0]["q_recente"]["derivados"]
    assert dv["base_12m_ebitda"] == "x4"
    assert dv["nd_ebitda_x"] == pytest.approx(600 / 400, abs=0.01)
    assert dv["janela_ttm"] is None


def test_ano_fiscal_nao_e_tocado_pelo_ttm():
    """FY ja e um periodo de 12 meses -- nao leva ajuste nenhum."""
    hist = [_tri(p) for p in ("2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1")]
    d = bd.enriquecer({"empresas": [_empresa(hist)]})["empresas"][0]
    assert d["fy2025"]["derivados"]["base_12m_ebitda"] == "fy"
    fy = d["fy2025"]
    assert fy["derivados"]["nd_ebitda_x"] == pytest.approx(
        fy["divida_liquida"] / fy["ebitda"], abs=0.01)


def test_meta_build_reporta_cobertura_de_ttm():
    hist = [_tri(p) for p in ("2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1")]
    d = bd.enriquecer({"empresas": [_empresa(hist), _empresa([])]})
    assert d["meta_build"]["empresas_com_ttm"] == 1
