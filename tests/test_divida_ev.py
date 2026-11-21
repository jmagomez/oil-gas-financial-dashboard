"""Divida liquida numa definicao so, com guarda de sinal, e EV com nao controladores.

Os casos sao os reais que motivaram as guardas: a TotalEnergies tinha +32.907 no
4T25, -34.142 no 1T26 e +30.991 no 2T26 (o 1T26 curado a mao, com a convencao
"Net Cash (Debt)" de agregador); a BP tinha 22.200 no FY2025 (a definicao dela,
sem arrendamentos) e 35.815 no 4T25 da serie.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import build_dashboard as bd

RAIZ = Path(__file__).resolve().parent.parent


def _e(historico, q_nd, fy_nd=None, ano=2025):
    return {
        "ticker": "TTE",
        "anual": {"ano": ano, "divida_liquida": fy_nd},
        "q_recente": {"trimestre": "Q3 2026", "divida_liquida": q_nd},
        "historico": [{"periodo": p, "divida_liquida": v} for p, v in historico],
    }


def test_troca_de_sinal_grande_entre_trimestres_e_acusada():
    e = _e([("2025-Q4", 32_907), ("2026-Q1", -34_142), ("2026-Q2", 30_991)], 25_188)
    avisos = bd.valida_divida_liquida([e])
    assert sum("troca de sinal" in a for a in avisos) == 2


def test_troca_de_sinal_perto_de_zero_e_plausivel():
    """A Equinor oscila perto do zero: de +4.000 para -2.000 nao e erro."""
    e = _e([("2026-Q1", 4_000), ("2026-Q2", -2_000)], 1_000)
    assert bd.valida_divida_liquida([e]) == []


def test_ano_fiscal_com_definicao_diferente_do_4t_e_acusado():
    e = _e([("2025-Q4", 35_815)], 26_563, fy_nd=22_200)
    assert any("FY2025" in a and "4T" in a for a in bd.valida_divida_liquida([e]))


def test_ano_fiscal_igual_ao_4t_nao_avisa():
    e = _e([("2025-Q4", 35_815)], 26_563, fy_nd=35_815)
    assert bd.valida_divida_liquida([e]) == []


def test_arquivo_vivo_sem_troca_de_sinal_e_com_fy_igual_ao_4t():
    dados = json.loads((RAIZ / "indicadores_oleo_gas.json").read_text(encoding="utf-8"))
    assert bd.valida_divida_liquida(dados["empresas"]) == []


# ---------------------------------------------------------------------------
# EV = market cap + divida liquida + nao controladores
# ---------------------------------------------------------------------------
def _empresa(nci_q=17_420, nci_q4=20_948):
    tri = {"receita": 1000, "lucro_liquido": 100, "ebitda": 200, "margem_liquida_pct": 10.0,
           "fluxo_caixa_operacional": 150, "fcf": 80, "capex": -70, "divida_liquida": 26_563,
           "divida_patrimonio_pct": 50.0, "roe_pct": 10.0, "roa_pct": 4.0, "producao_kboed": 2_220}
    return {
        "ticker": "BP", "nome": "BP", "pais": "X",
        "anual": dict(tri, ano=2025, divida_liquida=35_815),
        "q_recente": dict(tri, trimestre="Q3 2026", nao_controladores=nci_q),
        "mercado": {"market_cap": 110_109, "pe": 10.0, "dividend_yield_pct": 4.7, "preco_acao": 42.75},
        "historico": [{"periodo": "2025-Q4", "divida_liquida": 35_815, "nao_controladores": nci_q4}],
        "fontes": ["x"],
    }


def _deriva(e):
    return bd.enriquecer({"empresas": [copy.deepcopy(e)]})["empresas"][0]


def test_ev_soma_nao_controladores():
    d = _deriva(_empresa())["q_recente"]["derivados"]
    assert d["ev"] == 110_109 + 26_563 + 17_420
    assert d["ev_inclui_nao_controladores"] is True


def test_ev_do_ano_fiscal_usa_o_saldo_do_4t():
    d = _deriva(_empresa())["anual"]["derivados"]
    assert d["ev"] == 110_109 + 35_815 + 20_948


def test_sem_saldo_de_nao_controladores_o_ev_diz_que_nao_inclui():
    d = _deriva(_empresa(nci_q=None, nci_q4=None))["q_recente"]["derivados"]
    assert d["ev"] == 110_109 + 26_563
    assert d["ev_inclui_nao_controladores"] is False


@pytest.mark.parametrize("chave", ["anual", "q_recente"])
def test_ev_ebitda_usa_o_ev_com_nao_controladores(chave):
    d = _deriva(_empresa())[chave]["derivados"]
    assert d["ev_ebitda_x"] is not None
