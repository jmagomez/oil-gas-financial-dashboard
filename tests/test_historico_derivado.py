"""Testes da camada derivada por trimestre histórico.

Por que existe: o histórico guardava apenas campos primários, então margem,
conversão de caixa e intensidade de capex só existiam para o período corrente.
O leitor via o nível de hoje e nunca a tendência -- num setor cíclico, é a
tendência que separa oscilação de preço de erosão estrutural.

Nada aqui é estimado: todos os indicadores saem de razões entre campos do
próprio trimestre.
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import build_dashboard as bd  # noqa: E402


def _tri(periodo, receita=100.0, ebitda=40.0, lucro=10.0, fcf=12.0, fco=30.0,
         capex=-18.0, prod=1000.0):
    return {"periodo": periodo, "receita": receita, "lucro_liquido": lucro,
            "ebitda": ebitda, "fluxo_caixa_operacional": fco, "fcf": fcf,
            "capex": capex, "divida_liquida": 500.0, "producao_kboed": prod}


def _empresa(historico):
    return {"ticker": "TST", "nome": "Teste", "pais": "X",
            "fy2025": _tri("FY2025"),
            "q_recente": dict(_tri("x"), trimestre="Q2 2026"),
            "mercado": {"market_cap": 1000, "pe": 10.0, "ev_ebitda": 5.0,
                        "dividend_yield_pct": 2.0, "preco_acao": 20.0},
            "historico": historico, "fontes": ["x"]}


# ---------------------------------------------------------------------------
# Rotulo do trimestre: o historico usa "2026-Q1", q_recente usa "Q1 2026"
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("rotulo,esperado", [
    ("Q1 2026", 90), ("2026-Q1", 90),     # 2026 nao e bissexto
    ("Q2 2026", 91), ("2026-Q2", 91),
    ("Q3 2025", 92), ("2025-Q3", 92),
    ("Q4 2025", 92), ("2025-Q4", 92),
])
def test_dias_aceita_os_dois_formatos_de_rotulo(rotulo, esperado):
    """Sem isto o historico caia no padrao de 90 dias e os US$/boe saiam errados."""
    assert bd.dias_do_trimestre(rotulo) == esperado


def test_rotulo_irreconhecivel_cai_no_padrao():
    assert bd.dias_do_trimestre("sem data") == bd.DIAS_PERIODO["q_recente"]


# ---------------------------------------------------------------------------
# Calculo
# ---------------------------------------------------------------------------
def test_razoes_do_trimestre_batem_com_a_conta_direta():
    e = _empresa([_tri("2025-Q3", receita=200.0, ebitda=50.0, lucro=20.0,
                       fcf=15.0, fco=40.0, capex=-25.0)])
    bd.derivar_historico(e)
    d = e["historico"][0]["derivados"]
    assert d["margem_ebitda_pct"] == pytest.approx(25.0)
    assert d["margem_liquida_pct"] == pytest.approx(10.0)
    assert d["conversao_fcf_pct"] == pytest.approx(30.0)
    assert d["capex_fco_pct"] == pytest.approx(62.5)


def test_por_boe_usa_os_dias_do_trimestre_certo():
    """Q3 tem 92 dias; usar 90 inflaria o indicador em ~2%."""
    e = _empresa([_tri("2025-Q3", ebitda=92.0, prod=1000.0)])
    bd.derivar_historico(e)
    d = e["historico"][0]["derivados"]
    # 92e6 / (1000 * 1000 * 92) = 1.0
    assert d["ebitda_por_boe_usd"] == pytest.approx(1.0, abs=0.001)


def test_capex_entra_em_modulo():
    """Capex e negativo no arquivo; a intensidade tem de sair positiva."""
    e = _empresa([_tri("2025-Q3", capex=-30.0, fco=60.0)])
    bd.derivar_historico(e)
    assert e["historico"][0]["derivados"]["capex_fco_pct"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Ausencias: buraco continua buraco
# ---------------------------------------------------------------------------
def test_campo_ausente_vira_none_e_nao_zero():
    e = _empresa([_tri("2025-Q3", ebitda=None)])
    bd.derivar_historico(e)
    d = e["historico"][0]["derivados"]
    assert d["margem_ebitda_pct"] is None
    assert d["conversao_fcf_pct"] is None
    assert d["margem_liquida_pct"] is not None   # os outros seguem validos


def test_producao_ausente_nao_inventa_por_boe():
    e = _empresa([_tri("2025-Q3", prod=None)])
    bd.derivar_historico(e)
    d = e["historico"][0]["derivados"]
    assert d["ebitda_por_boe_usd"] is None
    assert d["receita_por_boe_usd"] is None


def test_receita_zero_nao_estoura():
    e = _empresa([_tri("2025-Q3", receita=0.0)])
    bd.derivar_historico(e)
    assert e["historico"][0]["derivados"]["margem_ebitda_pct"] is None


def test_historico_vazio_nao_quebra():
    e = _empresa([])
    bd.derivar_historico(e)
    assert e["historico"] == []


# ---------------------------------------------------------------------------
# Integracao
# ---------------------------------------------------------------------------
def test_enriquecer_aplica_a_camada_e_publica_as_chaves():
    hist = [_tri(p) for p in ("2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1")]
    d = bd.enriquecer({"empresas": [_empresa(hist)]})
    for h in d["empresas"][0]["historico"]:
        assert "derivados" in h
    # o template monta o seletor a partir desta lista, nao de lista fixa
    assert "margem_ebitda_pct" in d["meta_build"]["derivados_historico"]
    assert "capex_fco_pct" in d["meta_build"]["derivados_historico"]


def test_nao_entra_no_historico_o_que_exige_janela_de_12_meses():
    """ND/EBITDA e FCF yield precisam de TTM movel. Com 4 trimestres de
    historico o TTM so existiria para o ultimo -- 1 ponto em 4 nao e serie."""
    hist = [_tri(p) for p in ("2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1")]
    d = bd.enriquecer({"empresas": [_empresa(hist)]})
    chaves = d["meta_build"]["derivados_historico"]
    assert "nd_ebitda_x" not in chaves
    assert "fcf_yield_pct" not in chaves
