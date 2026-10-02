"""Testes da PoC de benchmarking trimestral (poc/build_poc.py)."""
import copy
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_poc", ROOT / "poc" / "build_poc.py")
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)


def _base():
    dados, empresas, base = bp.carrega()
    return dados, empresas, base


def test_base_tem_os_seis_trimestres_para_as_sete_empresas():
    _, _, base = _base()
    for t in bp.ORDEM_EMPRESAS:
        assert all(p in base[t] for p in bp.PERIODOS), t


def test_dados_atuais_nao_tem_vermelho_no_recorte_da_poc():
    dados, empresas, base = _base()
    log = bp.aplica_regras(dados, empresas, base)
    verm = [x for x in log.itens if x["severidade"] == "vermelho" and x["empresa"] in bp.POC_EMPRESAS]
    assert verm == []


def test_r8_pega_inversao_de_sinal_da_divida_liquida():
    dados, empresas, base = _base()
    empresas = copy.deepcopy(empresas)
    empresas["EQNR"]["fy2025"]["divida_liquida"] = -abs(base["EQNR"]["2025-Q4"]["divida_liquida"])
    log = bp.aplica_regras(dados, empresas, base)
    assert any(x["empresa"] == "EQNR" and x["regra"].startswith("R8") and x["severidade"] == "vermelho" for x in log.itens)


def test_r4_troca_de_sinal_material_vira_vermelho_e_contamina_o_indicador():
    dados, empresas, base = _base()
    base = copy.deepcopy(base)
    base["TTE"]["2026-Q1"]["divida_liquida"] = -34142
    log = bp.aplica_regras(dados, empresas, base)
    assert log.status_campo("TTE", "2026-Q1", "divida_liquida") == "vermelho"
    fato = bp.calcula(empresas, base, log)
    nd = [f for f in fato if f["empresa"] == "TTE" and f["periodo"] == "2026-Q1" and f["indicador"] == "nd_ebitda"][0]
    assert nd["status"] == "vermelho"


def test_r2_coerencia_fcf():
    dados, empresas, base = _base()
    base = copy.deepcopy(base)
    base["PBR"]["2025-Q3"]["fcf"] += 2000
    log = bp.aplica_regras(dados, empresas, base)
    assert log.status_campo("PBR", "2025-Q3", "fcf") == "vermelho"


def test_desvio_explicado_pelo_brent_nao_rebaixa_o_valor():
    dados, empresas, base = _base()
    log = bp.aplica_regras(dados, empresas, base)
    # 2T26: receita da Petrobras +43% com Brent +25% -> justificado
    alertas = [x for x in log.itens if x["empresa"] == "PBR" and x["periodo"] == "2026-Q2" and x["campo"] == "receita"]
    assert alertas and all(x["justificado"] for x in alertas)
    assert log.status_campo("PBR", "2026-Q2", "receita") == "verde"


def test_nd_ebitda_usa_ttm_a_partir_do_4t25():
    dados, empresas, base = _base()
    log = bp.aplica_regras(dados, empresas, base)
    fato = bp.calcula(empresas, base, log)
    f = [x for x in fato if x["empresa"] == "XOM" and x["periodo"] == "2026-Q2" and x["indicador"] == "nd_ebitda"][0]
    ttm = sum(base["XOM"][p]["ebitda"] for p in ["2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2"])
    assert abs(f["valor"] - base["XOM"]["2026-Q2"]["divida_liquida"] / ttm) < 0.01
    f1 = [x for x in fato if x["empresa"] == "XOM" and x["periodo"] == "2025-Q1" and x["indicador"] == "nd_ebitda"][0]
    assert f1["status"] != "verde" and "×4" in f1["obs"]


def test_efetivo_repete_ultimo_valor_anual_e_marca_ressalva():
    dados, empresas, base = _base()
    log = bp.aplica_regras(dados, empresas, base)
    fato = bp.calcula(empresas, base, log)
    ef = {x["periodo"]: x for x in fato if x["empresa"] == "XOM" and x["indicador"] == "efetivo"}
    assert ef["2025-Q2"]["valor"] == empresas["XOM"]["efetivo"]["2024-12-31"]
    assert ef["2026-Q2"]["valor"] == empresas["XOM"]["efetivo"]["2025-12-31"]
    assert ef["2025-Q4"]["status"] == "verde" and ef["2026-Q1"]["status"] == "amarelo"


def test_trimestre_novo_entra_sem_mudar_codigo():
    dados, empresas, base = _base()
    base = copy.deepcopy(base)
    for t in base:
        novo = dict(base[t]["2026-Q2"])
        base[t]["2026-Q3"] = novo
    periodos = bp.define_periodos(base)
    assert periodos[-1] == "2026-Q3" and periodos[0] == "2025-Q2" and len(periodos) == bp.JANELA
    log = bp.aplica_regras(dados, empresas, base)
    fato = bp.calcula(empresas, base, log)
    assert any(f["periodo"] == "2026-Q3" for f in fato)
    bp.carrega()  # restaura a janela original


def test_painel_publicado_esta_sincronizado_com_o_template():
    caminho = ROOT / "poc" / "painel_benchmarking_poc.html"
    if not caminho.exists():
        pytest.skip("painel ainda não gerado (o workflow gera após o merge)")
    html = caminho.read_text(encoding="utf-8")
    assert "__DATA__" not in html
    tpl = (ROOT / "poc" / "painel_template.html").read_text(encoding="utf-8")
    assert tpl.split("__DATA__")[0] in html
