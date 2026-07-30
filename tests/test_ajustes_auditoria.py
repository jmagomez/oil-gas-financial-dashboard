"""Testes dos ajustes de auditoria em build_dashboard e update_market_data."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_dashboard as bd  # noqa: E402
import update_market_data as umd  # noqa: E402


# --------------------------------------------------------------------------- #
# Dias do periodo (antes era 90 fixo para qualquer trimestre)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("rotulo,esperado", [
    ("Q1 2026", 90), ("Q2 2026", 91), ("Q3 2026", 92), ("Q4 2026", 92),
    ("Q1 2024", 91),  # bissexto
])
def test_dias_do_trimestre(rotulo, esperado):
    assert bd.dias_do_trimestre(rotulo) == esperado


def test_dias_do_trimestre_rotulo_estranho_usa_padrao():
    assert bd.dias_do_trimestre("sem trimestre") == bd.DIAS_PERIODO["q_recente"]


def test_dias_do_ano_bissexto():
    assert bd.dias_do_ano("FY2024") == 366
    assert bd.dias_do_ano("FY2025") == 365


# --------------------------------------------------------------------------- #
# Margem curada x margem calculada
# --------------------------------------------------------------------------- #
def _empresa(receita, lucro, margem):
    periodo = {
        "receita": receita, "lucro_liquido": lucro, "ebitda": receita * 0.2,
        "margem_liquida_pct": margem, "fluxo_caixa_operacional": 10.0, "fcf": 5.0,
        "capex": -5.0, "divida_liquida": 10.0, "divida_patrimonio_pct": 10.0,
        "roe_pct": 1.0, "roa_pct": 1.0, "producao_kboed": 100.0,
        "trimestre": "Q1 2026", "periodo": "FY2025",
    }
    return {
        "ticker": "TST", "nome": "Teste", "pais": "X",
        "fy2025": dict(periodo), "q_recente": dict(periodo),
        "mercado": {"market_cap": 1000.0, "pe": 10.0, "ev_ebitda": 5.0,
                    "dividend_yield_pct": 2.0, "preco_acao": 50.0},
        "fontes": ["teste"],
    }


def test_margem_divergente_e_reportada():
    """Caso real: BP FY2025 traz margem 0,68% com lucro/receita = 0,029%."""
    data = bd.enriquecer({"empresas": [_empresa(189335.0, 55.0, 0.68)]})
    problemas = bd.validate(data)
    assert any("margem_liquida_pct informada" in p for p in problemas)


def test_margem_coerente_nao_gera_aviso():
    data = bd.enriquecer({"empresas": [_empresa(1000.0, 100.0, 10.0)]})
    assert not any("margem_liquida_pct" in p for p in bd.validate(data))


# --------------------------------------------------------------------------- #
# Producao proxy visivel
# --------------------------------------------------------------------------- #
def test_producao_proxy_expoe_o_valor_usado():
    """Sem producao no ano fiscal, o CSV mostrava a coluna VAZIA ao lado de um
    US$/boe calculado com o proxy do trimestre."""
    e = _empresa(1000.0, 100.0, 10.0)
    e["fy2025"]["producao_kboed"] = None
    data = bd.enriquecer({"empresas": [e]})
    d = data["empresas"][0]["fy2025"]["derivados"]
    assert d["producao_proxy"] is True
    assert d["producao_usada_kboed"] == 100.0
    assert d["receita_por_boe_usd"] is not None


def test_sem_producao_em_lugar_nenhum_nao_inventa_por_boe():
    e = _empresa(1000.0, 100.0, 10.0)
    e["fy2025"]["producao_kboed"] = None
    e["q_recente"]["producao_kboed"] = None
    data = bd.enriquecer({"empresas": [e]})
    d = data["empresas"][0]["fy2025"]["derivados"]
    assert d["producao_proxy"] is False
    assert d["receita_por_boe_usd"] is None
    assert d["producao_usada_kboed"] is None


# --------------------------------------------------------------------------- #
# Campo congelado pelo limite de variacao
# --------------------------------------------------------------------------- #
def test_variacao_grande_e_rejeitada_por_padrao():
    ok, motivo = umd.valida("preco_acao", 200.0, 100.0)
    assert not ok and "variacao" in motivo


def test_forcar_destrava_movimento_real():
    ok, _ = umd.valida("preco_acao", 200.0, 100.0, forcar=True)
    assert ok


def test_forcar_nao_desliga_a_faixa_de_plausibilidade():
    """--forcar libera o limite de variacao, nao aceita numero absurdo."""
    ok, motivo = umd.valida("preco_acao", 99_999_999.0, 100.0, forcar=True)
    assert not ok and "faixa" in motivo
