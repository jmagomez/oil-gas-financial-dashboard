"""Ano fiscal como atributo da empresa: rotulo derivado, virada automatica, aviso de defasagem.

O ano estava escrito em ~40 lugares (a chave `fy2025` no JSON, no schema do app,
no template, no e-mail e no CSV). Estes testes garantem que nenhum deles volta e
que o 4T de um ano novo vira o bloco `anual` sozinho -- com os quatro
trimestres, ou nao vira.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import date
from pathlib import Path

import pytest

import build_dashboard as bd
import update_fundamentals as uf

RAIZ = Path(__file__).resolve().parent.parent


def _tri(periodo, receita=100, lucro=10, div=5, rec=None, nd=500, nci=40, prod=1000):
    return {
        "periodo": periodo, "receita": receita, "lucro_liquido": lucro, "ebitda": 30,
        "fluxo_caixa_operacional": 20, "fcf": 8, "capex": -12, "dividendos_pagos": div,
        "recompras": rec, "divida_liquida": nd, "nao_controladores": nci, "producao_kboed": prod,
    }


def _empresa_no_4t(historico):
    q = dict(_tri("x", receita=130, nd=450, nci=44, prod=1040), trimestre="Q4 2026",
             divida_patrimonio_pct=30.0, roe_pct=12.5, roa_pct=6.1, margem_liquida_pct=7.69)
    q.pop("periodo")
    return {"ticker": "TST", "anual": {"ano": 2025, "receita": 999}, "q_recente": q, "historico": historico}


SERIE_2026 = [_tri("2025-Q4"), _tri("2026-Q1", rec=3), _tri("2026-Q2", rec=3), _tri("2026-Q3", rec=3)]


def test_4t_com_os_quatro_trimestres_vira_o_ano():
    e = _empresa_no_4t(copy.deepcopy(SERIE_2026))
    assert uf.promove_ano_fiscal(e) == 2026
    a = e["anual"]
    assert a["ano"] == 2026
    assert a["receita"] == 100 * 3 + 130          # fluxo: soma dos quatro
    assert a["divida_liquida"] == 450             # saldo: o do 4T
    assert a["nao_controladores"] == 44
    assert a["roe_pct"] == 12.5                   # ja e 12 meses no 4T
    assert a["margem_liquida_pct"] == pytest.approx(40 / 430 * 100, abs=0.01)
    assert a["producao_kboed"] == round((1000 * 3 + 1040) / 4)
    assert e["proveniencia"]["anual"]["trimestres"] == ["2026-Q1", "2026-Q2", "2026-Q3", "2026-Q4"]


def test_fluxo_ausente_em_um_trimestre_deixa_o_do_ano_ausente_e_nao_parcial():
    e = _empresa_no_4t(copy.deepcopy(SERIE_2026))  # recompra do 4T e None
    uf.promove_ano_fiscal(e)
    assert e["anual"]["recompras"] is None
    assert e["anual"]["dividendos_pagos"] == 20


def test_sem_os_quatro_trimestres_nao_vira():
    e = _empresa_no_4t([t for t in copy.deepcopy(SERIE_2026) if t["periodo"] != "2026-Q2"])
    assert uf.promove_ano_fiscal(e) is None
    assert e["anual"] == {"ano": 2025, "receita": 999}


@pytest.mark.parametrize("trimestre,ano_atual", [("Q3 2026", 2025), ("Q4 2026", 2026)])
def test_fora_do_4t_ou_ano_ja_promovido_nao_mexe(trimestre, ano_atual):
    e = _empresa_no_4t(copy.deepcopy(SERIE_2026))
    e["q_recente"]["trimestre"] = trimestre
    e["anual"]["ano"] = ano_atual
    assert uf.promove_ano_fiscal(e) is None


def test_reescreve_o_bloco_anual_so_de_quem_virou():
    bruto = (RAIZ / "indicadores_oleo_gas.json").read_text(encoding="utf-8")
    dados = json.loads(bruto)
    xom = next(e for e in dados["empresas"] if e["ticker"] == "XOM")
    xom["anual"] = {c: None for c in uf.CAMPOS_ANUAL} | {"ano": 2026, "receita": 1}
    novo = uf.reescreve_json(bruto, dados, {"XOM", "CVX"}, date(2027, 2, 5), anos_promovidos={"XOM"})
    lido = {e["ticker"]: e for e in json.loads(novo)["empresas"]}
    assert lido["XOM"]["anual"]["ano"] == 2026
    assert lido["CVX"]["anual"]["ano"] == 2025
    # A linha anual da CVX fica byte a byte igual.
    linha = lambda t, txt: re.search(r'"anual": \{[^}]*\}', txt[txt.index(f'"ticker": "{t}"'):]).group(0)  # noqa: E731
    assert linha("CVX", novo) == linha("CVX", bruto)


# ---------------------------------------------------------------------------
# Build: rotulo derivado e aviso de defasagem
# ---------------------------------------------------------------------------
def _e(t, ano, tri):
    return {"ticker": t, "anual": {"ano": ano}, "q_recente": {"trimestre": tri}}


def test_anos_fiscais_misto_diz_quem_esta_onde():
    af = bd.anos_fiscais([_e("XOM", 2026, "Q4 2026"), _e("PBR", 2025, "Q3 2026")])
    assert af["uniforme"] is False
    assert af["empresas_por_ano"] == {2025: ["PBR"], 2026: ["XOM"]}


@pytest.mark.parametrize("ano,tri,defasado", [
    (2025, "Q3 2026", False),   # o FY2026 ainda nao fechou
    (2025, "Q4 2026", True),    # fechou e nao virou
    (2025, "Q1 2027", True),
    (2026, "Q1 2027", False),
])
def test_ano_fiscal_defasado(ano, tri, defasado):
    assert bd.ano_fiscal_defasado(_e("X", ano, tri)) is defasado


def test_nenhum_consumidor_volta_a_escrever_o_ano():
    """A chave `fy2025` e o texto `periodo_anual` nao podem voltar."""
    arquivos = [
        "build_dashboard.py", "build_email.py", "update_fundamentals.py", "update_market_data.py",
        "dashboard_template.html", "indicadores_oleo_gas.json",
        *map(str, (RAIZ / "app" / "src").rglob("*.ts*")),
    ]
    for nome in arquivos:
        texto = (RAIZ / nome).read_text(encoding="utf-8")
        # Uso (chave, acesso), nao prosa: a docstring que conta a historia pode citar o nome.
        assert not re.search(r"""["']fy2025["']|\.fy2025\b|["']periodo_anual["']|\.periodo_anual\b""", texto), nome
        assert "'FY2025'" not in texto and '"FY2025"' not in texto, nome
