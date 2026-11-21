"""Coleta da Petrobras pela CVM e conversao pela PTAX.

Nenhum teste toca a rede: os zips de ITR/DFP sao montados em memoria, no layout
do Portal de Dados Abertos, com os valores REAIS dos releases da companhia
(tests/fixtures/cvm_pbr_release.json). A PTAX e a do arquivo de verdade.

As ancoras externas sao numeros que a propria Petrobras divulga em DOLAR. E
contra eles que a regra de conversao e conferida -- nao contra a saida do codigo.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pytest

import coleta_cvm as cvm
import ptax

FIX = json.loads((Path(__file__).parent / "fixtures" / "cvm_pbr_release.json").read_text(encoding="utf-8"))
TRI = FIX["trimestres"]
BAL = FIX["balanco_construido"]
CAB = ["CD_CVM", "VERSAO", "ESCALA_MOEDA", "ORDEM_EXERC", "DT_INI_EXERC", "DT_FIM_EXERC",
       "CD_CONTA", "DS_CONTA", "VL_CONTA"]
DRE_CONTAS = (
    ("3.01", "Receita de Venda de Bens e/ou Serviços", "receita_brl"),
    ("3.06", "Resultado Financeiro", "resultado_financeiro_brl"),
    ("3.07", "Resultado Antes dos Tributos sobre o Lucro", "lair_brl"),
    ("3.11.01", "Atribuído a Sócios da Empresa Controladora", "lucro_liquido_brl"),
)


def _linha(conta, desc, valor_milhoes, fim, ini="", versao=1, ordem="ÚLTIMO", cd="009512"):
    # A CVM entrega em MIL reais; o fixture esta em milhoes.
    return [cd, versao, "MIL", ordem, ini, fim, conta, desc, f"{valor_milhoes * 1000:.2f}"]


def _acumulado(campo, ano, ate_q):
    return sum(TRI[f"{ano}-Q{q}"][campo] for q in range(1, ate_q + 1))


def _demonstracoes(periodos):
    """Linhas de DRE (isolada), DFC (so acumulada, como no ITR real) e balanco."""
    dre, dfc, bpa, bpp = [], [], [], []
    for p in periodos:
        v, ano, q = TRI[p], int(p[:4]), int(p[-1])
        fim, ini, jan = cvm._fim(p), cvm._ini(p), f"{ano}-01-01"
        for conta, desc, campo in DRE_CONTAS:
            dre.append(_linha(conta, desc, v[campo], fim, ini))
        for conta, desc, campo, sinal in (
            ("6.01", "Caixa Líquido Atividades Operacionais", "fco_brl", 1),
            ("6.01.01.03", "Depreciação, depleção e amortização", "da_brl", 1),
            ("6.02.01", "Aquisições de ativos imobilizados e intangíveis", "capex_brl", -1),
        ):
            dfc.append(_linha(conta, desc, sinal * _acumulado(campo, ano, q), fim, jan))
        bruta = v["divida_liquida_brl"] + BAL["caixa"] + BAL["titulos_cp"] + BAL["titulos_lp"]
        bpa += [
            _linha("1", "Ativo Total", BAL["ativos"], fim),
            _linha("1.01.01", "Caixa e Equivalentes de Caixa", BAL["caixa"], fim),
            _linha("1.01.02", "Aplicações Financeiras", BAL["titulos_cp"], fim),
            _linha("1.02.01.03", "Aplicações Financeiras Avaliadas ao Custo Amortizado", BAL["titulos_lp"], fim),
        ]
        bpp += [
            _linha("2.01.04.01", "Empréstimos e Financiamentos", 40000, fim),
            _linha("2.02.01.01", "Empréstimos e Financiamentos", bruta - 40000 - BAL["arrendamentos"], fim),
            _linha("2.02.02.02.03", "Arrendamentos", BAL["arrendamentos"], fim),
            _linha("2.03", "Patrimônio Líquido Consolidado", BAL["patrimonio"], fim),
        ]
    return {"DRE": dre, "DFC_MI": dfc, "BPA": bpa, "BPP": bpp}


def _zip(doc, ano, tabelas):
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w") as z:
        for demo, linhas in tabelas.items():
            txt = io.StringIO()
            w = csv.writer(txt, delimiter=";", lineterminator="\n")
            w.writerow(CAB)
            w.writerows(linhas)
            z.writestr(f"{doc}_cia_aberta_{demo}_con_{ano}.csv", txt.getvalue().encode("latin-1"))
            # A demonstracao INDIVIDUAL (so a controladora) vem no mesmo zip, com
            # os mesmos codigos de conta. Aqui ela vai com valores dobrados e
            # versao 9: se o leitor a abrisse, ela VENCERIA a consolidada na
            # regra de reapresentacao e todos os testes de valor quebrariam.
            ind = io.StringIO()
            wi = csv.writer(ind, delimiter=";", lineterminator="\n")
            wi.writerow(CAB)
            wi.writerows([r[:1] + [9] + r[2:8] + [f"{float(r[8]) * 2:.2f}"] for r in linhas])
            z.writestr(f"{doc}_cia_aberta_{demo}_ind_{ano}.csv", ind.getvalue().encode("latin-1"))
    return mem.getvalue()


@pytest.fixture(scope="module")
def ls():
    """ITR de 2025 (1T-3T), DFP de 2025 (ano cheio) e ITR de 2026 (1T-2T)."""
    itr25 = _demonstracoes(["2025-Q1", "2025-Q2", "2025-Q3"])
    # O ITR tambem traz a DRE acumulada, de onde sai o "nove meses".
    for q in (2, 3):
        for c, d, k in DRE_CONTAS:
            itr25["DRE"].append(_linha(c, d, _acumulado(k, 2025, q), cvm._fim(f"2025-Q{q}"), "2025-01-01"))
    dfp25 = _demonstracoes(["2025-Q4"])
    # Na DFP a DRE e do ANO, nao do trimestre: o 4T sai por diferenca.
    dfp25["DRE"] = [_linha(c, d, _acumulado(k, 2025, 4), "2025-12-31", "2025-01-01") for c, d, k in DRE_CONTAS]
    itr26 = _demonstracoes(["2026-Q1", "2026-Q2"])
    return (cvm.linhas(_zip("itr", 2025, itr25)) + cvm.linhas(_zip("dfp", 2025, dfp25))
            + cvm.linhas(_zip("itr", 2026, itr26)))


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("p", sorted(TRI))
def test_le_cada_trimestre_em_reais(ls, p):
    """Inclui os dois casos dificeis: DFC por diferenca de acumulados e o 4T pela DFP."""
    b, v = cvm.trimestre_brl(ls, p), TRI[p]
    assert b["receita"] == pytest.approx(v["receita_brl"])
    assert b["lucro_liquido"] == pytest.approx(v["lucro_liquido_brl"])
    assert b["fco"] == pytest.approx(v["fco_brl"])
    assert b["capex"] == pytest.approx(v["capex_brl"])
    assert b["divida_total"] - b["caixa"] == pytest.approx(v["divida_liquida_brl"])


@pytest.mark.parametrize("p", sorted(TRI))
def test_ebitda_e_o_da_resolucao_cvm_156(ls, p):
    """LAIR - resultado financeiro + D&A, que e o EBITDA que a companhia divulga."""
    assert cvm.trimestre_brl(ls, p)["ebitda"] == pytest.approx(TRI[p]["ebitda_brl"], abs=1)


def test_outra_companhia_no_mesmo_zip_nao_e_lida():
    tabelas = {"DRE": [_linha("3.01", "Receita", 999, "2026-06-30", "2026-04-01", cd="004170")]}
    assert cvm.linhas(_zip("itr", 2026, tabelas)) == []


def test_coluna_do_exercicio_anterior_nao_e_lida():
    """O ITR repete o mesmo trimestre do ano passado como comparativo (PENULTIMO)."""
    tabelas = {"DRE": [_linha("3.01", "Receita", 999, "2025-06-30", "2025-04-01", ordem="PENÚLTIMO")]}
    assert cvm.linhas(_zip("itr", 2026, tabelas)) == []


def test_reapresentacao_substitui_a_versao_original():
    tabelas = {"DRE": [_linha("3.01", "Receita", 100, "2026-06-30", "2026-04-01", versao=1),
                       _linha("3.01", "Receita", 120, "2026-06-30", "2026-04-01", versao=2)]}
    lidas = cvm.linhas(_zip("itr", 2026, tabelas))
    assert [x["valor"] for x in lidas] == [120]


def test_ultimo_periodo_e_o_mais_recente_com_dre(ls):
    assert cvm.ultimo_periodo(ls) == "2026-Q2"


# ---------------------------------------------------------------------------
# Conversao -- conferida contra o que a Petrobras divulga em dolar
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("p", sorted(TRI))
def test_divida_pelo_FECHAMENTO_bate_com_a_divulgada_em_dolar(ls, p):
    """Seis trimestres, seis numeros publicados pela companhia, tolerancia de 0,5%.

    E o teste que sustenta a regra "saldo pelo fechamento": nao compara o codigo
    consigo mesmo, compara com o release.
    """
    usd = cvm.converte(cvm.trimestre_brl(ls, p), ptax.taxas(p))
    assert usd["divida_total"] - usd["caixa"] == pytest.approx(TRI[p]["divida_liquida_usd"], rel=0.005)


def test_fluxos_pela_MEDIA_batem_com_os_divulgados_em_dolar(ls):
    """2T26: lucro US$ 10,4 bi, EBITDA US$ 18,6 bi, FCO US$ 12,3 bi no release."""
    usd = cvm.converte(cvm.trimestre_brl(ls, "2026-Q2"), ptax.taxas("2026-Q2"))
    div = FIX["usd_divulgado_bi_2026_Q2"]
    assert usd["lucro_liquido"] / 1000 == pytest.approx(div["lucro_liquido"], abs=0.05)
    assert usd["ebitda"] / 1000 == pytest.approx(div["ebitda_ajustado"], abs=0.05)
    assert usd["fco"] / 1000 == pytest.approx(div["fco"], abs=0.1)


def test_trocar_media_por_fechamento_NAO_passaria_despercebido(ls):
    """A divida pela media erraria o numero divulgado em mais de 2%."""
    b, t = cvm.trimestre_brl(ls, "2026-Q2"), ptax.taxas("2026-Q2")
    pela_media = (b["divida_total"] - b["caixa"]) / t["media"]
    assert abs(pela_media / TRI["2026-Q2"]["divida_liquida_usd"] - 1) > 0.02


# ---------------------------------------------------------------------------
# Formato do pipeline
# ---------------------------------------------------------------------------
def test_bruto_sai_em_dolar_com_a_conversao_registrada(ls):
    bruto = cvm.monta_bruto(ls)
    assert bruto["fim"] == date(2026, 6, 30)
    assert bruto["moeda"] == "USD"
    assert "CVM" in bruto["fonte"]
    c = bruto["conversao"]
    assert c["moeda_origem"] == "BRL"
    assert (c["ptax_media"], c["ptax_fechamento"]) == (5.0494, 5.1766)
    # Os reais de origem ficam ao lado: quem audita refaz a divisao.
    assert c["receita_brl"] == 169530
    assert bruto["linhas"]["receita"] == pytest.approx(169530 / 5.0494)


def test_lucro_de_12_meses_converte_cada_trimestre_pela_sua_media(ls):
    """Somar em reais e dividir por uma taxa so misturaria quatro cambios."""
    quatro = ("2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2")
    bruto = cvm.monta_bruto(ls)
    esperado = sum(TRI[p]["lucro_liquido_brl"] / ptax.taxas(p)["media"] for p in quatro)
    assert bruto["ttm"]["lucro_liquido"] == pytest.approx(esperado)
    uma_taxa_so = sum(TRI[p]["lucro_liquido_brl"] for p in quatro) / 5.0494
    assert abs(uma_taxa_so / esperado - 1) > 0.02


def test_traz_os_trimestres_anteriores_para_o_backfill(ls):
    fins = [a["fim"] for a in cvm.monta_bruto(ls)["anteriores"]]
    assert fins == [date(2026, 3, 31), date(2025, 12, 31), date(2025, 9, 30), date(2025, 6, 30)]


def test_sem_ptax_do_trimestre_nao_ha_conversao(ls):
    """Sem a taxa certa o trimestre nao sai -- nem com a taxa do trimestre vizinho."""
    so_ate_marco = {d: v for d, v in ptax.le().items() if d < date(2026, 4, 1)}
    with pytest.raises(ptax.PtaxIncompleta):
        cvm.monta_bruto(ls, cotacoes=so_ate_marco)


def test_zip_sem_a_companhia_devolve_none():
    assert cvm.monta_bruto([]) is None


# ---------------------------------------------------------------------------
# Dividendos e recompras da DFC de financiamento
# ---------------------------------------------------------------------------
def _dfc_financiamento(linhas_por_trimestre):
    """ITR de 2026 com DFC acumulada; cada item: (conta, descricao, {periodo: valor_isolado})."""
    dfc = []
    for conta, desc, por_tri in linhas_por_trimestre:
        acumulado = 0.0
        for p in ("2026-Q1", "2026-Q2"):
            acumulado += por_tri[p]
            dfc.append(_linha(conta, desc, acumulado, cvm._fim(p), "2026-01-01"))
    return cvm.linhas(_zip("itr", 2026, {"DFC_MI": dfc}))


def test_dividendos_da_petrobras_saem_da_dfc_sem_os_de_nao_controladores():
    """O yield divide pelo market cap DA Petrobras: dividendo a minoritario de subsidiaria nao entra."""
    ls = _dfc_financiamento([
        ("6.03.03", "Dividendos pagos a acionistas da Petrobras", {"2026-Q1": -12_000, "2026-Q2": -18_000}),
        ("6.03.04", "Dividendos pagos a acionistas não controladores", {"2026-Q1": -300, "2026-Q2": -400}),
    ])
    b = cvm.trimestre_brl(ls, "2026-Q2")
    assert b["dividendos"] == pytest.approx(18_000)  # trimestre isolado, por diferenca de acumulados


def test_sem_linha_de_recompra_na_dfc_a_recompra_e_zero():
    """A DFC entregue a CVM e completa: sem a linha, nao houve recompra."""
    ls = _dfc_financiamento([
        ("6.03.03", "Dividendos pagos a acionistas da Petrobras", {"2026-Q1": -12_000, "2026-Q2": -18_000}),
    ])
    assert cvm.trimestre_brl(ls, "2026-Q2")["recompras"] == 0.0


def test_recompra_quando_existe_e_lida_e_positiva():
    ls = _dfc_financiamento([
        ("6.03.03", "Dividendos pagos a acionistas da Petrobras", {"2026-Q1": -12_000, "2026-Q2": -18_000}),
        ("6.03.06", "Recompra de ações", {"2026-Q1": -1_000, "2026-Q2": -2_500}),
    ])
    assert cvm.trimestre_brl(ls, "2026-Q2")["recompras"] == pytest.approx(2_500)


def test_dividendos_e_recompras_sao_fluxos_convertidos_pela_media():
    brl = {"dividendos": 18_000.0, "recompras": 0.0}
    t = ptax.taxas("2026-Q2")
    usd = cvm.converte(brl, t)
    assert usd["dividendos"] == pytest.approx(18_000 / t["media"])
    assert usd["recompras"] == 0.0
