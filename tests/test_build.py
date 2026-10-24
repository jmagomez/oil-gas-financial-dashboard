"""Testes da camada de indicadores derivados e da geração dos artefatos."""
import csv
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

import build_dashboard as bd  # noqa: E402


@pytest.fixture(scope="module")
def dados():
    raw = json.loads((ROOT / "tests" / "fixtures" / "indicadores_snapshot.json").read_text(encoding="utf-8"))
    return bd.enriquecer(raw)


def empresa_sintetica(receita, lucro, margem):
    """Uma empresa minima e completa, para os casos que o snapshot nao cobre."""
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


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def test_div_protege_denominador_zero_e_none():
    assert bd.div(10, 0) is None
    assert bd.div(None, 5) is None
    assert bd.div(10, None) is None
    assert bd.div(10, 4) == 2.5


def test_dias_do_ano_conta_o_bissexto():
    assert bd.dias_do_ano("FY2024") == 366
    assert bd.dias_do_ano("FY2025") == 365


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
    """A camada derivada vive só em memória — o arquivo de dados continua limpo.

    Confere as duas coisas: que nenhum derivado está gravado no arquivo, e que
    rodar `enriquecer` não escreve nada nele (a troca da margem exibida por
    `consolidar_margem` acontece no payload, não na fonte).
    """
    bruto = (ROOT / "indicadores_oleo_gas.json").read_text(encoding="utf-8")
    raw = json.loads(bruto)
    assert "derivados" not in raw["empresas"][0]["fy2025"]
    assert "meta_build" not in raw
    bd.enriquecer(json.loads(bruto))
    assert (ROOT / "indicadores_oleo_gas.json").read_text(encoding="utf-8") == bruto


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
    """Sem producao no ano fiscal, o CSV mostrava a coluna VAZIA ao lado de um
    US$/boe calculado com o proxy do trimestre — quem lesse nao tinha como saber.
    """
    eqnr = next(e for e in dados["empresas"] if e["ticker"] == "EQNR")
    d = eqnr["fy2025"]["derivados"]
    assert eqnr["fy2025"]["producao_kboed"] is None
    assert d["producao_proxy"] is True
    assert d["producao_usada_kboed"] == eqnr["q_recente"]["producao_kboed"]
    assert d["receita_por_boe_usd"] is not None


def test_sem_producao_em_lugar_nenhum_nao_inventa_por_boe():
    e = empresa_sintetica(1000.0, 100.0, 10.0)
    e["fy2025"]["producao_kboed"] = None
    e["q_recente"]["producao_kboed"] = None
    d = bd.enriquecer({"empresas": [e]})["empresas"][0]["fy2025"]["derivados"]
    assert d["producao_proxy"] is False
    assert d["producao_usada_kboed"] is None
    assert d["receita_por_boe_usd"] is None


# --------------------------------------------------------------------------- #
# Margem exibida: lucro ATRIBUIVEL / receita, nao a margem da fonte
# --------------------------------------------------------------------------- #
def test_margem_exibida_e_a_recalculada():
    """Caso BP FY2025, conferido no 6-K da propria BP (US$ milhoes):

        receita 189.335 | profit for the period 1.295 | nao-controladores 1.240
        | atribuivel aos acionistas 55

    1.295/189.335 = 0,68% (o que a fonte trazia);  55/189.335 = 0,03%.
    """
    p = bd.enriquecer({"empresas": [empresa_sintetica(189335.0, 55.0, 0.68)]})
    p = p["empresas"][0]["fy2025"]
    assert p["margem_liquida_pct"] == pytest.approx(0.03, abs=0.005)
    assert p["margem_liquida_fonte_pct"] == 0.68


def test_divergencia_de_margem_e_reportada_sem_descartar_a_fonte():
    data = bd.enriquecer({"empresas": [empresa_sintetica(189335.0, 55.0, 0.68)]})
    problemas = bd.validate(data)
    assert any("margem da fonte" in p and "nao-controladores" in p for p in problemas)


def test_margem_ja_coerente_fica_intacta_e_sem_aviso():
    data = bd.enriquecer({"empresas": [empresa_sintetica(1000.0, 100.0, 10.0)]})
    assert data["empresas"][0]["fy2025"]["margem_liquida_pct"] == pytest.approx(10.0)
    assert not any("margem da fonte" in x for x in bd.validate(data))


def test_fcf_yield_usa_fcf_anualizado(dados):
    shel = next(e for e in dados["empresas"] if e["ticker"] == "SHEL")
    q = shel["q_recente"]
    esperado = round(q["fcf"] * 4 / shel["mercado"]["market_cap"] * 100, 2)
    assert q["derivados"]["fcf_yield_pct"] == esperado


def test_payout_sobre_fcf_nao_volta_como_indicador_proprio(dados):
    """Guard: payout_fcf_pct era 100 / cobertura_dividendo_x, exatamente.

    Os dois eram publicados lado a lado — duas colunas da tabela, duas do CSV e
    dois lugares na contagem de indicadores do badge para uma informacao so.
    Ficou a cobertura, que e a leitura padrao de credito (quantas vezes o caixa
    cobre o compromisso). Se o payout voltar, que volte por uma razao nova, nao
    por recalculo acidental da mesma razao.
    """
    for e in dados["empresas"]:
        for per in ("fy2025", "q_recente"):
            assert "payout_fcf_pct" not in e[per]["derivados"], e["ticker"]
    assert "payout_fcf_pct" not in bd.CSV_HEADER


def test_run_rate_zero_quando_trimestre_e_um_quarto_do_ano():
    d = bd.derivar_empresa({"fy2025": {"ebitda": 100}, "q_recente": {"ebitda": 25}})
    assert d["run_rate_ebitda_pct"] == 0


def test_run_rate_e_o_unico_derivado_de_empresa():
    """Guard: receita, lucro e FCF tinham run-rate calculado e nunca exibido.

    So o EBITDA chega a tela (cartao de KPI). Se outro run-rate voltar, deve
    voltar junto com o lugar onde e lido.
    """
    d = bd.derivar_empresa({"fy2025": {"ebitda": 100}, "q_recente": {"ebitda": 40}})
    assert set(d) == {"run_rate_ebitda_pct"}
    assert d["run_rate_ebitda_pct"] == 60.0


def test_run_rate_sem_ano_fiscal_fica_nulo_em_vez_de_estourar():
    assert bd.derivar_empresa({"fy2025": {"ebitda": 0}, "q_recente": {"ebitda": 9}})[
        "run_rate_ebitda_pct"] is None
    assert bd.derivar_empresa({"fy2025": {}, "q_recente": {}})["run_rate_ebitda_pct"] is None


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
    assert any(ln[idx] not in ("", None) for ln in linhas[1:])


def test_historico_e_opcional_e_normalizado(dados):
    # A versao anterior assertava `tem_historico is False`, ou seja, afirmava
    # que NENHUMA empresa tem historico -- e quebrava no instante em que a
    # funcionalidade passasse a funcionar. O contrato real e que a flag
    # ESPELHE os dados, com historico ou sem.
    for e in dados["empresas"]:
        assert isinstance(e["historico"], list)
    esperado = any(e["historico"] for e in dados["empresas"])
    assert dados["meta_build"]["tem_historico"] is esperado
