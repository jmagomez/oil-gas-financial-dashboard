"""Remuneracao ao acionista em caixa: shareholder yield, dividend yield de caixa e o detector de ADR.

Contexto em update_fundamentals.CAMPOS_DISTRIBUICAO. Numeros da Shell abaixo sao
os do caso real: US$ 0,3906 por acao ORDINARIA por trimestre (6-K de 29/10/2026)
e 1 ADS = 2 ordinarias.
"""

from __future__ import annotations

import copy

import pytest

import build_dashboard as bd


def _tri(periodo, div=2_000, rec=3_500, fco=12_000):
    return {
        "periodo": periodo, "receita": 60_000, "lucro_liquido": 5_000, "ebitda": 15_000,
        "fluxo_caixa_operacional": fco, "fcf": fco - 5_000, "capex": -5_000,
        "dividendos_pagos": div, "recompras": rec, "divida_liquida": 40_000, "producao_kboed": 2_500,
    }


def _empresa(ticker="SHEL", market_cap=264_000, yield_mercado=1.64, **kw):
    q = dict(_tri("x", **kw), trimestre="Q3 2026")
    q.pop("periodo")
    return {
        "ticker": ticker, "nome": ticker, "pais": "X",
        "anual": dict(_tri("FY2025", div=8_000, rec=14_000, fco=48_000), ano=2025),
        "q_recente": q,
        "mercado": {"market_cap": market_cap, "pe": 9.0, "dividend_yield_pct": yield_mercado, "preco_acao": 93.58},
        "historico": [_tri("2025-Q4", **kw), _tri("2026-Q1", **kw), _tri("2026-Q2", **kw)],
        "fontes": ["x"],
    }


def _deriva(*empresas):
    return bd.enriquecer({"empresas": [copy.deepcopy(e) for e in empresas]})


def test_shareholder_yield_soma_dividendos_e_recompras_de_12_meses():
    d = _deriva(_empresa())["empresas"][0]["q_recente"]["derivados"]
    # 4 x (2.000 + 3.500) = 22.000 sobre 264.000
    assert d["shareholder_yield_pct"] == pytest.approx(22_000 / 264_000 * 100, abs=0.01)
    assert d["dividend_yield_caixa_pct"] == pytest.approx(8_000 / 264_000 * 100, abs=0.01)
    assert d["distribuicao_fco_pct"] == pytest.approx(22_000 / 48_000 * 100, abs=0.01)
    assert d["recompras_12m"] == 14_000


def test_cobertura_usa_o_dividendo_PAGO_e_diz_isso():
    d = _deriva(_empresa())["empresas"][0]["q_recente"]["derivados"]
    assert d["base_dividendo"] == "caixa_12m"
    assert d["dividendos_estimados"] == 8_000
    assert d["cobertura_dividendo_x"] == pytest.approx(4 * 7_000 / 8_000, abs=0.01)


def test_sem_janela_completa_nao_inventa_e_volta_para_a_estimativa_declarada():
    e = _empresa()
    e["historico"][0]["recompras"] = None
    d = _deriva(e)["empresas"][0]["q_recente"]["derivados"]
    assert d["shareholder_yield_pct"] is None
    assert d["dividend_yield_caixa_pct"] is not None  # dividendos completos continuam valendo
    e["historico"][0]["dividendos_pagos"] = None
    d = _deriva(e)["empresas"][0]["q_recente"]["derivados"]
    assert d["dividend_yield_caixa_pct"] is None
    assert d["base_dividendo"] == "estimado_yield_mercado"


def test_ano_fiscal_nao_ganha_yield_de_caixa_sem_dado_anual():
    d = _deriva(_empresa())["empresas"][0]["anual"]["derivados"]
    assert d["shareholder_yield_pct"] is None
    assert d["base_dividendo"] == "estimado_yield_mercado"


# ---------------------------------------------------------------------------
# Radar: a base e do CONJUNTO, nunca misturada
# ---------------------------------------------------------------------------
def test_radar_usa_shareholder_yield_quando_todas_tem():
    dados = _deriva(_empresa("SHEL"), _empresa("BP", market_cap=110_000, div=1_300, rec=750))
    assert dados["meta_build"]["base_retorno_acionista"]["chave"] == "shareholder_yield"


def test_radar_nao_mistura_bases_entre_empresas():
    """Uma sem recompra conhecida derruba o conjunto inteiro para a base seguinte."""
    sem_rec = _empresa("BP")
    sem_rec["q_recente"]["recompras"] = None
    dados = _deriva(_empresa("SHEL"), sem_rec)
    assert dados["meta_build"]["base_retorno_acionista"]["chave"] == "dividend_yield_caixa"


def test_shell_deixa_de_ser_a_pior_em_retorno_quando_recompra_entra():
    """O caso real: so por dividend yield de mercado (1,64%, com o erro de ADR) a Shell tirava zero.

    Com dividendos + recompras pagos, ela e quem mais devolve ao acionista.
    """
    shell = _empresa("SHEL", market_cap=264_000, yield_mercado=1.64, div=2_200, rec=5_000)
    xom = _empresa("XOM", market_cap=652_000, yield_mercado=2.59, div=4_300, rec=5_000)
    dados = _deriva(shell, xom)
    perfil = {e["ticker"]: e["perfil"]["Retorno ao acionista"] for e in dados["empresas"]}
    assert perfil["SHEL"] == 100.0 and perfil["XOM"] == 0.0


# ---------------------------------------------------------------------------
# Detector da armadilha de ADR
# ---------------------------------------------------------------------------
def test_validacao_acusa_yield_de_mercado_com_a_razao_do_ads():
    # Dividendo da Shell por ADS: 2 x 4 x 0,3906 = 3,12; market cap tal que o caixa da ~3,3%
    shell = _empresa("SHEL", market_cap=264_000, yield_mercado=1.64, div=2_200, rec=5_000)
    problemas = bd.validate(_deriva(shell))
    alerta = [p for p in problemas if "razão de ADR" in p]
    assert alerta and "SHEL" in alerta[0] and "2.0" in alerta[0].replace(",", ".")


def test_validacao_fica_quieta_quando_mercado_e_caixa_concordam():
    xom = _empresa("XOM", market_cap=652_000, yield_mercado=2.65, div=4_300, rec=5_000)
    assert not [p for p in bd.validate(_deriva(xom)) if "razão de ADR" in p]


# ---------------------------------------------------------------------------
# Concentracao de recompras (Equinor: fatia do Estado recomprada de uma vez)
# ---------------------------------------------------------------------------
def test_concentracao_e_o_maior_trimestre_sobre_os_12_meses():
    e = _empresa()
    e["historico"][0]["recompras"] = 10_500  # 2025-Q4 vira o pico
    d = _deriva(e)["empresas"][0]["q_recente"]["derivados"]
    # janela 4T25..3T26: 10.500 + 3 x 3.500 = 21.000; o pico e metade
    assert d["concentracao_recompras_pct"] == 50


def test_concentracao_sem_recompra_fica_nula():
    d = _deriva(_empresa(rec=0))["empresas"][0]["q_recente"]["derivados"]
    assert d["concentracao_recompras_pct"] is None
