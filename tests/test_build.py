"""Testes da camada de indicadores derivados e da geração dos artefatos."""
import csv
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import build_dashboard as bd  # noqa: E402


@pytest.fixture(scope="module")
def dados():
    raw = json.loads((ROOT / "tests" / "fixtures" / "indicadores_snapshot.json").read_text(encoding="utf-8"))
    return bd.enriquecer(raw)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def test_div_protege_denominador_zero_e_none():
    assert bd.div(10, 0) is None
    assert bd.div(None, 5) is None
    assert bd.div(10, None) is None
    assert bd.div(10, 4) == 2.5


def test_pct_converte_para_percentual():
    assert bd.pct(1, 4) == 25.0
    assert bd.pct(None, 4) is None


# --------------------------------------------------------------------------- #
# Estrutura do payload enriquecido
# --------------------------------------------------------------------------- #
def test_todas_empresas_ganham_derivados(dados):
    for e in dados["empresas"]:
        assert "derivados" in e
        assert "perfil" in e
        for periodo in ("fy2025", "q_recente"):
            assert "derivados" in e[periodo], f"{e['ticker']} {periodo}"


def test_json_primario_nao_e_alterado_no_disco():
    """A camada derivada vive só em memória — o arquivo de dados continua limpo."""
    raw = json.loads((ROOT / "indicadores_oleo_gas.json").read_text(encoding="utf-8"))
    assert "derivados" not in raw["empresas"][0]["fy2025"]
    assert "meta_build" not in raw


# --------------------------------------------------------------------------- #
# Correção dos cálculos
# --------------------------------------------------------------------------- #
def test_margem_ebitda_bate_com_calculo_manual(dados):
    xom = next(e for e in dados["empresas"] if e["ticker"] == "XOM")
    p = xom["fy2025"]
    esperado = round(p["ebitda"] / p["receita"] * 100, 2)
    assert p["derivados"]["margem_ebitda_pct"] == esperado


def test_nd_ebitda_usa_ebitda_anualizado_no_trimestre(dados):
    pbr = next(e for e in dados["empresas"] if e["ticker"] == "PBR")
    q = pbr["q_recente"]
    esperado = round(q["divida_liquida"] / (q["ebitda"] * 4), 2)
    assert q["derivados"]["nd_ebitda_x"] == esperado


def test_enterprise_value_soma_divida_liquida(dados):
    for e in dados["empresas"]:
        p = e["fy2025"]
        assert p["derivados"]["ev"] == round(e["mercado"]["market_cap"] + p["divida_liquida"])


def test_caixa_liquido_gera_ev_menor_que_market_cap(dados):
    """Equinor e TotalEnergies têm dívida líquida negativa."""
    for tk in ("EQNR", "TTE"):
        e = next(x for x in dados["empresas"] if x["ticker"] == tk)
        assert e["fy2025"]["derivados"]["ev"] < e["mercado"]["market_cap"]


def test_receita_por_boe_em_ordem_de_grandeza_plausivel(dados):
    """Receita por barril equivalente deve ficar numa faixa realista (US$ 10–500)."""
    for e in dados["empresas"]:
        v = e["fy2025"]["derivados"]["receita_por_boe_usd"]
        assert v is not None, e["ticker"]
        assert 10 < v < 500, f"{e['ticker']}: {v} US$/boe fora da faixa esperada"


def test_producao_ausente_usa_proxy_do_trimestre(dados):
    eqnr = next(e for e in dados["empresas"] if e["ticker"] == "EQNR")
    assert eqnr["fy2025"]["producao_kboed"] is None
    assert eqnr["fy2025"]["derivados"]["producao_proxy"] is True
    assert eqnr["fy2025"]["derivados"]["receita_por_boe_usd"] is not None


def test_fcf_yield_usa_fcf_anualizado(dados):
    shel = next(e for e in dados["empresas"] if e["ticker"] == "SHEL")
    q = shel["q_recente"]
    esperado = round(q["fcf"] * 4 / shel["mercado"]["market_cap"] * 100, 2)
    assert q["derivados"]["fcf_yield_pct"] == esperado


def test_cobertura_de_dividendo_e_payout_sao_inversos(dados):
    for e in dados["empresas"]:
        d = e["fy2025"]["derivados"]
        cob, pay = d["cobertura_dividendo_x"], d["payout_fcf_pct"]
        if cob and pay:
            assert abs(cob * pay / 100 - 1) < 0.02, e["ticker"]


def test_run_rate_zero_quando_trimestre_e_um_quarto_do_ano():
    empresa = {
        "fy2025": {"receita": 400, "ebitda": 100, "lucro_liquido": 40, "fcf": 20,
                   "divida_liquida": 10, "margem_liquida_pct": 10},
        "q_recente": {"receita": 100, "ebitda": 25, "lucro_liquido": 10, "fcf": 5,
                      "divida_liquida": 10, "margem_liquida_pct": 10},
    }
    d = bd.derivar_empresa(empresa)
    assert d["run_rate_receita_pct"] == 0
    assert d["run_rate_ebitda_pct"] == 0
    assert d["delta_divida_liquida"] == 0


def test_scores_do_radar_ficam_entre_0_e_100_com_extremos(dados):
    eixos = dados["meta_build"]["eixos_perfil"]
    for eixo in eixos:
        valores = [e["perfil"][eixo] for e in dados["empresas"] if e["perfil"][eixo] is not None]
        assert valores, eixo
        assert min(valores) == 0 and max(valores) == 100, f"{eixo} não foi normalizado"
        assert all(0 <= v <= 100 for v in valores)


def test_score_de_valuation_premia_multiplo_menor(dados):
    """Menor EV/EBITDA do grupo deve receber score 100 no eixo Valuation."""
    barata = min(dados["empresas"], key=lambda e: e["mercado"]["ev_ebitda"])
    assert barata["perfil"]["Valuation"] == 100


# --------------------------------------------------------------------------- #
# Validação e artefatos
# --------------------------------------------------------------------------- #
def test_validacao_roda_e_retorna_lista(dados):
    problemas = bd.validate(dados)
    assert isinstance(problemas, list)
    assert all(isinstance(p, str) for p in problemas)


def test_template_tem_placeholder():
    assert "__DATA_JSON__" in (ROOT / "dashboard_template.html").read_text(encoding="utf-8")


def test_build_html_injeta_o_payload_no_template(dados, tmp_path, monkeypatch):
    """Gera o HTML num diretório temporário e confere o resultado da injeção."""
    saida = tmp_path / "dashboard.html"
    monkeypatch.setattr(bd, "HTML_OUT_PATH", saida)
    bd.build_html(dados)
    html = saida.read_text(encoding="utf-8")
    assert "__DATA_JSON__" not in html
    assert "const DATA = {" in html
    # os derivados precisam chegar ao HTML, não só ao CSV
    assert "nd_ebitda_x" in html and "eixos_perfil" in html
    for tk in ("XOM", "PBR", "EQNR"):
        assert tk in html


def test_html_publicado_nao_tem_placeholder():
    html = (ROOT / "dashboard_oleo_gas.html").read_text(encoding="utf-8")
    assert "__DATA_JSON__" not in html, "rode build_dashboard.py para regenerar o HTML"
    assert "const DATA = {" in html


def test_csv_gerado_tem_cabecalho_e_derivados():
    with (ROOT / "indicadores_oleo_gas.csv").open(encoding="utf-8") as f:
        linhas = list(csv.reader(f))
    assert linhas[0] == bd.CSV_HEADER
    # 7 empresas x 2 períodos + cabeçalho
    assert len(linhas) == 15
    idx = bd.CSV_HEADER.index("nd_ebitda_x")
    assert any(l[idx] not in ("", None) for l in linhas[1:])


def test_historico_e_opcional_e_normalizado(dados):
    # A versao anterior assertava `tem_historico is False`, ou seja, afirmava
    # que NENHUMA empresa tem historico -- e quebrava no instante em que a
    # funcionalidade passasse a funcionar. O contrato real e que a flag
    # ESPELHE os dados, com historico ou sem.
    for e in dados["empresas"]:
        assert isinstance(e["historico"], list)
    esperado = any(e["historico"] for e in dados["empresas"])
    assert dados["meta_build"]["tem_historico"] is esperado
