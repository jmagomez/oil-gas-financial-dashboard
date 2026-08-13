"""Testes da coleta de fundamentos trimestrais.

Nenhum teste toca a rede. O caso central usa os numeros REAIS do 2T26 da
ExxonMobil, conferidos a mao na fonte padronizada (stockanalysis.com, dados
Fiscal.ai, atualizados em 31/07/2026) antes de virarem fixture:

    receita 114.529 | lucro 14.525 | EBIT 18.163 | FCO 23.555
    capex -6.527    | FCF 17.028   | divida total 42.368 | caixa 10.588

Se a traducao das demonstracoes quebrar, este teste falha com numeros que
alguem ja verificou -- e nao contra a propria saida do codigo.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

# Os testes de coleta montam DataFrames iguais aos que o yfinance devolve.
# Sem este guarda, a ausencia de pandas viraria erro de COLETA e deixaria a
# suite inteira vermelha. Com ele, vira skip -- mas ATENCAO: o skip e do
# MODULO todo (~41 testes), nao de 3. Por isso pandas esta em
# requirements-dev.txt: senao o CI ficaria verde sem testar nada disto.
pd = pytest.importorskip("pandas")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import update_fundamentals as uf  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
XOM_Q2_2026 = {
    "receita": 114_529,
    "lucro_liquido": 14_525,
    "ebit": 18_163,
    "depreciacao": 6_100,
    "fco": 23_555,
    "capex": -6_527,
    "fcf": 17_028,
    "divida_total": 42_368,
    "caixa": 10_588,
    "investimentos_curto": 0,
    "patrimonio": 259_957,
    "ativos": 476_000,
}


def _bruto(linhas: dict | None = None, fim: date = date(2026, 6, 30), ttm: dict | None = None):
    base = dict(XOM_Q2_2026)
    base.update(linhas or {})
    return {"fim": fim, "linhas": base, "ttm": ttm if ttm is not None else {"lucro_liquido": 32_781}}


# Snapshot congelado: ver tests/fixtures/LEIA-ME.md. Assertar sobre o arquivo
# vivo faria a atualizacao dos dados quebrar a suite.
SNAPSHOT = Path(__file__).resolve().parent / "fixtures" / "indicadores_snapshot.json"


@pytest.fixture()
def dados():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _coletado(ticker="XOM", **kwargs):
    return {ticker: _bruto(**kwargs)}


# ---------------------------------------------------------------------------
# Rotulos de periodo
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "fim,esperado",
    [
        (date(2026, 3, 31), "Q1 2026"),
        (date(2026, 6, 30), "Q2 2026"),
        (date(2026, 9, 30), "Q3 2026"),
        (date(2025, 12, 31), "Q4 2025"),
    ],
)
def test_rotulo_do_trimestre(fim, esperado):
    assert uf.rotulo_trimestre(fim) == esperado


def test_historico_usa_rotulo_que_ordena_cronologicamente():
    """O grafico ordena periodos como texto -- "Q1 2026" quebraria a linha."""
    rotulos = [uf.rotulo_historico(t) for t in ["Q1 2026", "Q2 2025", "Q4 2025", "Q2 2026"]]
    assert sorted(rotulos) == ["2025-Q2", "2025-Q4", "2026-Q1", "2026-Q2"]
    # E o formato ingenuo, para contraste, ordenaria errado:
    assert sorted(["Q1 2026", "Q2 2025"]) == ["Q1 2026", "Q2 2025"]


def test_comparacao_de_trimestres():
    assert uf.e_mais_novo("Q2 2026", "Q1 2026")
    assert uf.e_mais_novo("Q1 2026", "Q4 2025")
    assert not uf.e_mais_novo("Q1 2026", "Q1 2026")
    assert not uf.e_mais_novo("Q4 2025", "Q1 2026")


# ---------------------------------------------------------------------------
# Traducao das demonstracoes: numeros conferidos a mao
# ---------------------------------------------------------------------------
def test_traduz_o_2t26_da_exxon_com_os_numeros_verificados():
    bloco = uf.monta_trimestre(_bruto())
    assert bloco["trimestre"] == "Q2 2026"
    assert bloco["receita"] == 114_529
    assert bloco["lucro_liquido"] == 14_525
    assert bloco["fluxo_caixa_operacional"] == 23_555
    assert bloco["capex"] == -6_527
    assert bloco["fcf"] == 17_028
    # Divida liquida publicada: 42.368 - 10.588 = 31.780
    assert bloco["divida_liquida"] == 31_780


def test_margem_e_recalculada_e_nao_copiada_da_fonte():
    """A margem publicada pela fonte nao fecha com os proprios numeros dela.

    A fonte publica "Profit Margin" de 12,99% para o 2T26 da Exxon, mas divide
    o lucro por uma receita menor que a linha "Revenue" que ela mesma exibe
    (114.529). Com os dois numeros que guardamos, a conta da 12,68%.

    Guardar 12,99% ao lado de receita 114.529 e lucro 14.525 deixaria o JSON
    internamente contraditorio, e a checagem de coerencia acusaria a cada build.
    Por isso a margem e sempre recalculada dos campos que ficam gravados.
    """
    bloco = uf.monta_trimestre(_bruto())
    assert bloco["margem_liquida_pct"] == pytest.approx(14_525 / 114_529 * 100, abs=0.01)
    assert uf.valida_coerencia(bloco) == []


def test_ebitda_cai_para_ebit_mais_depreciacao_quando_a_linha_falta():
    bloco = uf.monta_trimestre(_bruto())
    assert bloco["ebitda"] == XOM_Q2_2026["ebit"] + XOM_Q2_2026["depreciacao"]


def test_ebitda_direto_tem_precedencia_sobre_o_calculo():
    bloco = uf.monta_trimestre(_bruto({"ebitda": 25_000}))
    assert bloco["ebitda"] == 25_000


def test_capex_e_sempre_negativo():
    assert uf.monta_trimestre(_bruto({"capex": 6_527}))["capex"] == -6_527


def test_fcf_e_derivado_quando_a_fonte_nao_publica():
    bloco = uf.monta_trimestre(_bruto({"fcf": None}))
    assert bloco["fcf"] == 23_555 - 6_527


def test_divida_liquida_desconta_caixa_e_aplicacoes():
    bloco = uf.monta_trimestre(_bruto({"caixa": 8_000, "investimentos_curto": 2_588}))
    assert bloco["divida_liquida"] == 42_368 - 10_588


def test_roe_e_roa_usam_lucro_de_doze_meses():
    """Trimestre isolado daria um retorno ~4x menor e incomparavel com o ano."""
    bloco = uf.monta_trimestre(_bruto(), ttm={"lucro_liquido": 32_781})
    assert bloco["roe_pct"] == pytest.approx(32_781 / 259_957 * 100, abs=0.01)
    assert bloco["roa_pct"] == pytest.approx(32_781 / 476_000 * 100, abs=0.01)


def test_sem_ttm_o_retorno_fica_nulo_em_vez_de_errado():
    bloco = uf.monta_trimestre(_bruto(), ttm={})
    assert bloco["roe_pct"] is None and bloco["roa_pct"] is None


def test_divida_patrimonio_em_percentual():
    bloco = uf.monta_trimestre(_bruto())
    assert bloco["divida_patrimonio_pct"] == pytest.approx(42_368 / 259_957 * 100, abs=0.1)


# ---------------------------------------------------------------------------
# Leitura dos DataFrames do yfinance
# ---------------------------------------------------------------------------
def _df(linhas: dict, colunas):
    return pd.DataFrame(linhas, index=colunas).T


def test_le_dataframes_e_converte_para_milhoes():
    colunas = [pd.Timestamp("2026-06-30"), pd.Timestamp("2026-03-31")]
    income = _df({"Total Revenue": [114_529e6, 83_161e6], "Net Income": [14_525e6, 4_183e6]}, colunas)
    cash = _df({"Operating Cash Flow": [23_555e6, 8_705e6], "Capital Expenditure": [-6_527e6, -6_470e6]}, colunas)
    balance = _df({"Total Debt": [42_368e6, 47_661e6], "Cash And Cash Equivalents": [10_588e6, 8_435e6]}, colunas)

    bruto = uf.coleta_bruto(income, cash, balance)
    assert bruto["fim"] == date(2026, 6, 30)
    assert bruto["linhas"]["receita"] == pytest.approx(114_529)
    assert bruto["linhas"]["fco"] == pytest.approx(23_555)
    assert bruto["linhas"]["divida_total"] == pytest.approx(42_368)


def test_ttm_so_e_calculado_com_quatro_trimestres_completos():
    colunas = [pd.Timestamp("2026-06-30"), pd.Timestamp("2026-03-31")]
    income = _df({"Total Revenue": [1e6, 1e6], "Net Income": [1e6, 1e6]}, colunas)
    bruto = uf.coleta_bruto(income, None, None)
    assert bruto["ttm"] == {}  # so 2 trimestres: nao inventa um TTM parcial


def test_demonstracao_vazia_devolve_none():
    assert uf.coleta_bruto(pd.DataFrame(), None, None) is None


# ---------------------------------------------------------------------------
# Validacao de coerencia -- o numero plausivel no campo errado
# ---------------------------------------------------------------------------
def test_ebitda_maior_que_receita_e_incoerente():
    avisos = uf.valida_coerencia({"receita": 100, "ebitda": 150})
    assert any("EBITDA" in a for a in avisos)


def test_fcf_que_nao_fecha_com_fco_menos_capex_e_incoerente():
    avisos = uf.valida_coerencia({"fluxo_caixa_operacional": 100, "capex": -30, "fcf": 90})
    assert any("FCF" in a for a in avisos)


def test_fcf_dentro_da_tolerancia_passa():
    assert uf.valida_coerencia({"fluxo_caixa_operacional": 100, "capex": -30, "fcf": 70.5}) == []


def test_margem_que_nao_bate_com_lucro_sobre_receita_e_incoerente():
    avisos = uf.valida_coerencia({"receita": 1000, "lucro_liquido": 100, "margem_liquida_pct": 25})
    assert any("margem" in a for a in avisos)


def test_bloco_da_exxon_e_coerente():
    assert uf.valida_coerencia(uf.monta_trimestre(_bruto())) == []


def test_faixa_pega_valor_absurdo():
    problemas = dict(uf.valida_campos({"receita": 999_999_999}))
    assert "receita" in problemas


# ---------------------------------------------------------------------------
# Rotacao de trimestre
# ---------------------------------------------------------------------------
def test_trimestre_novo_rotaciona_para_o_historico(dados):
    anterior = dados["empresas"][0]["q_recente"]["trimestre"]
    saida, rel = uf.aplica_fundamentos(dados, _coletado())
    xom = saida["empresas"][0]

    assert xom["q_recente"]["trimestre"] == "Q2 2026"
    assert xom["q_recente"]["receita"] == 114_529
    assert [h["periodo"] for h in xom["historico"]] == [uf.rotulo_historico(anterior)]
    assert xom["historico"][0]["receita"] == 83_160  # o 1T26 que estava em q_recente
    assert len(rel.novos) == 1 and rel.novos[0]["para"] == "Q2 2026"


def test_mesmo_trimestre_nao_sobrescreve_dado_curado(dados):
    coletado = _coletado(fim=date(2026, 3, 31))
    saida, rel = uf.aplica_fundamentos(dados, coletado)
    assert saida["empresas"][0]["q_recente"] == dados["empresas"][0]["q_recente"]
    assert saida["empresas"][0]["historico"] == []
    assert rel.novos == []
    assert any(d["ticker"] == "XOM" for d in rel.divergencias)


def test_divergencia_grande_no_mesmo_trimestre_vira_aviso(dados):
    saida, rel = uf.aplica_fundamentos(dados, _coletado(fim=date(2026, 3, 31)))
    campos = {d["campo"] for d in rel.divergencias}
    assert "receita" in campos  # 114.529 da fonte vs 83.160 curado


def test_empresa_sem_resposta_fica_intacta(dados):
    saida, rel = uf.aplica_fundamentos(dados, {})
    assert saida["empresas"] == dados["empresas"]
    assert len(rel.falhas) == len(dados["empresas"])


def test_producao_e_preservada_e_marcada_como_carregada(dados):
    producao_antes = dados["empresas"][0]["q_recente"]["producao_kboed"]
    saida, _ = uf.aplica_fundamentos(dados, _coletado())
    xom = saida["empresas"][0]
    assert xom["q_recente"]["producao_kboed"] == producao_antes
    prov = xom["proveniencia"]["producao_kboed"]
    assert prov["trimestre_do_dado"] == "Q1 2026"
    assert "carregado" in prov["observacao"]


def test_incoerencia_descarta_a_empresa_inteira(dados):
    """Meio balanco errado e pior que nenhum."""
    saida, rel = uf.aplica_fundamentos(dados, _coletado(linhas={"fcf": 1_000}))
    assert saida["empresas"][0]["q_recente"]["trimestre"] == "Q1 2026"  # nao rotacionou
    assert rel.novos == []
    assert any("incoerentes" in f["detalhe"] for f in rel.falhas)


def test_campo_fora_de_faixa_vira_nulo_e_o_resto_entra(dados):
    saida, rel = uf.aplica_fundamentos(dados, _coletado(linhas={"divida_patrimonio_pct": None, "patrimonio": 1}))
    # patrimonio ridiculo estoura divida/patrimonio, mas o trimestre entra
    assert saida["empresas"][0]["q_recente"]["trimestre"] == "Q2 2026"
    assert saida["empresas"][0]["q_recente"]["divida_patrimonio_pct"] is None
    assert any(r["campo"] == "divida_patrimonio_pct" for r in rel.rejeicoes)


def test_entrada_nao_e_modificada(dados):
    copia = json.loads(json.dumps(dados))
    uf.aplica_fundamentos(dados, _coletado())
    assert dados == copia


def test_ordem_dos_campos_do_trimestre_e_preservada(dados):
    saida, _ = uf.aplica_fundamentos(dados, _coletado())
    assert list(saida["empresas"][0]["q_recente"].keys()) == uf.CAMPOS_TRIMESTRE


def test_historico_acumulado_fica_em_ordem(dados):
    """Dois trimestres seguidos empilham na ordem certa."""
    passo1, _ = uf.aplica_fundamentos(dados, _coletado())
    passo2, _ = uf.aplica_fundamentos(passo1, _coletado(fim=date(2026, 9, 30)))
    xom = passo2["empresas"][0]
    assert [h["periodo"] for h in xom["historico"]] == ["2026-Q1", "2026-Q2"]
    assert xom["q_recente"]["trimestre"] == "Q3 2026"


# ---------------------------------------------------------------------------
# Integracao com o build
# ---------------------------------------------------------------------------
def test_saida_continua_digerivel_pelo_build(dados):
    import build_dashboard as bd

    saida, _ = uf.aplica_fundamentos(dados, _coletado())
    enriquecido = bd.enriquecer(saida)
    xom = enriquecido["empresas"][0]
    assert xom["q_recente"]["derivados"]["margem_ebitda_pct"] == pytest.approx(
        24_263 / 114_529 * 100, abs=0.1
    )


def test_historico_preenchido_liga_a_secao_de_series(dados):
    import build_dashboard as bd

    assert bd.enriquecer(dados)["meta_build"]["tem_historico"] is False
    saida, _ = uf.aplica_fundamentos(dados, _coletado())
    assert bd.enriquecer(saida)["meta_build"]["tem_historico"] is True


# ---------------------------------------------------------------------------
# Backfill do historico
# ---------------------------------------------------------------------------
def _com_anteriores(fins):
    b = _bruto()
    b["anteriores"] = [
        {"fim": f, "linhas": dict(XOM_Q2_2026, receita=100_000 + i), "ttm": {}}
        for i, f in enumerate(fins)
    ]
    return {"XOM": b}


def test_backfill_preenche_varios_trimestres_de_uma_vez(dados):
    """Sem isso a serie historica levaria um ano para ficar util."""
    coletado = _com_anteriores([date(2026, 3, 31), date(2025, 12, 31), date(2025, 9, 30)])
    saida, _ = uf.aplica_fundamentos(dados, coletado)
    periodos = [h["periodo"] for h in saida["empresas"][0]["historico"]]
    assert periodos == ["2025-Q3", "2025-Q4", "2026-Q1"]


def test_backfill_nao_sobrescreve_o_trimestre_curado(dados):
    """O 1T26 que sai de q_recente vale mais que a versao da fonte."""
    curado = dados["empresas"][0]["q_recente"]["receita"]
    saida, _ = uf.aplica_fundamentos(dados, _com_anteriores([date(2026, 3, 31)]))
    q1 = next(h for h in saida["empresas"][0]["historico"] if h["periodo"] == "2026-Q1")
    assert q1["receita"] == curado


def test_backfill_ignora_trimestre_igual_ou_mais_novo_que_o_atual(dados):
    saida, _ = uf.aplica_fundamentos(dados, _com_anteriores([date(2026, 6, 30), date(2026, 9, 30)]))
    periodos = [h["periodo"] for h in saida["empresas"][0]["historico"]]
    assert periodos == ["2026-Q1"]  # so o que saiu de q_recente


def test_backfill_descarta_trimestre_incoerente(dados):
    coletado = _com_anteriores([date(2025, 12, 31)])
    coletado["XOM"]["anteriores"][0]["linhas"]["fcf"] = 999_999
    saida, _ = uf.aplica_fundamentos(dados, coletado)
    assert [h["periodo"] for h in saida["empresas"][0]["historico"]] == ["2026-Q1"]
