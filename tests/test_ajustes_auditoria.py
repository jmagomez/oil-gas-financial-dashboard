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
    assert any("margem da fonte" in p for p in problemas)


def test_margem_coerente_nao_gera_aviso():
    data = bd.enriquecer({"empresas": [_empresa(1000.0, 100.0, 10.0)]})
    assert not any("margem da fonte" in p for p in bd.validate(data))


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


# --------------------------------------------------------------------------- #
# Margem exibida passa a ser a recalculada (lucro atribuivel / receita)
# --------------------------------------------------------------------------- #
def test_margem_exibida_e_a_recalculada():
    """Caso BP FY2025, conferido no 6-K da propria BP:

        receita 189.335 | profit for the period 1.295 | nao-controladores 1.240
        | atribuivel aos acionistas 55

    1.295/189.335 = 0,68% (o que a fonte trazia);  55/189.335 = 0,03%.
    """
    data = bd.enriquecer({"empresas": [_empresa(189335.0, 55.0, 0.68)]})
    p = data["empresas"][0]["fy2025"]
    assert p["margem_liquida_pct"] == pytest.approx(0.03, abs=0.005)
    assert p["margem_liquida_fonte_pct"] == 0.68


def test_valor_da_fonte_e_preservado_e_a_divergencia_reportada():
    data = bd.enriquecer({"empresas": [_empresa(189335.0, 55.0, 0.68)]})
    problemas = bd.validate(data)
    assert any("margem da fonte" in p and "nao-controladores" in p for p in problemas)


def test_margem_ja_coerente_fica_intacta():
    data = bd.enriquecer({"empresas": [_empresa(1000.0, 100.0, 10.0)]})
    p = data["empresas"][0]["fy2025"]
    assert p["margem_liquida_pct"] == pytest.approx(10.0)
    assert not any("margem da fonte" in x for x in bd.validate(data))


def test_json_primario_nao_e_alterado():
    """A troca acontece so no payload em memoria."""
    import json
    antes = json.loads(bd.JSON_PATH.read_text(encoding="utf-8"))
    bd.enriquecer(json.loads(bd.JSON_PATH.read_text(encoding="utf-8")))
    depois = json.loads(bd.JSON_PATH.read_text(encoding="utf-8"))
    assert antes == depois



# --------------------------------------------------------------------------- #
# Validacao do campo `historico` (preenchido a mao)
# --------------------------------------------------------------------------- #
def _com_historico(itens):
    e = _empresa(1000.0, 100.0, 10.0)
    e["historico"] = itens
    return bd.enriquecer({"empresas": [e]})


def test_historico_vazio_mantem_secao_escondida():
    data = bd.enriquecer({"empresas": [_empresa(1000.0, 100.0, 10.0)]})
    assert data["meta_build"]["tem_historico"] is False


def test_historico_preenchido_destrava_a_secao():
    data = _com_historico([{"periodo": "FY2024", "receita": 100.0, "ebitda": 20.0}])
    assert data["meta_build"]["tem_historico"] is True


def test_historico_pega_campo_com_typo():
    problemas = bd.validate(_com_historico([{"periodo": "FY2024", "lucro_liq": 5.0}]))
    assert any("reconhecido" in p for p in problemas)


def test_historico_pega_periodo_fora_do_formato():
    problemas = bd.validate(_com_historico([{"periodo": "2024", "receita": 100.0}]))
    assert any("FY####" in p for p in problemas)


def test_historico_pega_periodo_duplicado():
    problemas = bd.validate(_com_historico([
        {"periodo": "FY2024", "receita": 100.0},
        {"periodo": "FY2024", "receita": 110.0},
    ]))
    assert any("duplicado" in p for p in problemas)


def test_historico_pega_capex_positivo():
    """No resto do arquivo capex e negativo; trocar o sinal inverteria capex/FCO."""
    problemas = bd.validate(_com_historico([{"periodo": "FY2024", "capex": 50.0}]))
    assert any("capex positivo" in p for p in problemas)


def test_historico_pega_valor_nao_numerico():
    problemas = bd.validate(_com_historico([{"periodo": "FY2024", "receita": "cem"}]))
    assert any("num" in p for p in problemas)


def test_historico_bem_preenchido_nao_gera_aviso():
    problemas = bd.validate(_com_historico([{
        "periodo": "FY2024", "receita": 1000.0, "lucro_liquido": 90.0, "ebitda": 200.0,
        "fluxo_caixa_operacional": 150.0, "fcf": 100.0, "capex": -50.0,
        "divida_liquida": 300.0, "producao_kboed": 100.0,
    }]))
    assert not any("hist" in p.lower() for p in problemas)



# --------------------------------------------------------------------------- #
# Trimestre por empresa (antes o template usava o rotulo de empresas[0])
# --------------------------------------------------------------------------- #
def _duas(tri_a, tri_b):
    a = _empresa(1000.0, 100.0, 10.0); a["ticker"] = "AAA"
    b = _empresa(1000.0, 100.0, 10.0); b["ticker"] = "BBB"
    a["q_recente"]["trimestre"] = tri_a
    b["q_recente"]["trimestre"] = tri_b
    return bd.enriquecer({"empresas": [a, b]})


def test_trimestres_iguais_nao_marcam_mistura():
    data = _duas("Q2 2026", "Q2 2026")
    assert data["meta_build"]["trimestres_mistos"] is False
    assert not any("trimestres diferentes" in p for p in bd.validate(data))


def test_trimestres_diferentes_sao_marcados_e_reportados():
    """Caso real: BP divulga em 04/08 e Petrobras em 06/08, depois das outras cinco."""
    data = _duas("Q2 2026", "Q1 2026")
    assert data["meta_build"]["trimestres_mistos"] is True
    avisos = [p for p in bd.validate(data) if "trimestres diferentes" in p]
    assert avisos and "AAA" in avisos[0] and "BBB" in avisos[0]


def test_meta_build_expoe_o_trimestre_de_cada_empresa():
    data = _duas("Q2 2026", "Q1 2026")
    assert data["meta_build"]["trimestres"] == {"AAA": "Q2 2026", "BBB": "Q1 2026"}


def test_q_recente_sem_rotulo_e_reportado():
    e = _empresa(1000.0, 100.0, 10.0)
    del e["q_recente"]["trimestre"]
    problemas = bd.validate(bd.enriquecer({"empresas": [e]}))
    assert any("sem r" in p and "trimestre" in p for p in problemas)
