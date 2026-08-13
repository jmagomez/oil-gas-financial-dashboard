"""Testes da rotina de atualizacao de dados de mercado.

Nenhum teste toca a rede: a camada de rede vive so em `busca_cotacoes`, e
aqui alimentamos o resto do modulo com respostas fabricadas.
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from datetime import date
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import update_market_data as umd  # noqa: E402


SNAPSHOT = RAIZ / "tests" / "fixtures" / "indicadores_snapshot.json"


@pytest.fixture()
def dados():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


@pytest.fixture()
def bruto():
    return SNAPSHOT.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Normalizacao do dividend yield -- o erro de 100x mais comum nessa API
# ---------------------------------------------------------------------------
def test_yield_calculado_a_partir_do_dividendo_anual():
    info = {"trailingAnnualDividendRate": 4.12, "regularMarketPrice": 148.36}
    assert umd.normaliza_yield(info, 148.36) == pytest.approx(2.777, abs=1e-3)


def test_yield_em_fracao_vira_percentual():
    assert umd.normaliza_yield({"dividendYield": 0.0278}, None) == pytest.approx(2.78)


def test_yield_ja_em_percentual_e_preservado():
    assert umd.normaliza_yield({"dividendYield": 2.78}, None) == pytest.approx(2.78)


def test_yield_prefere_trailing_annual_a_campo_ambiguo():
    info = {"dividendYield": 999, "trailingAnnualDividendYield": 0.0375}
    assert umd.normaliza_yield(info, None) == pytest.approx(3.75)


def test_yield_ausente_devolve_none():
    assert umd.normaliza_yield({}, 100.0) is None


# ---------------------------------------------------------------------------
# Extracao e unidades
# ---------------------------------------------------------------------------
def test_market_cap_convertido_de_unidades_para_milhoes():
    campos = umd.extrai_campos({"marketCap": 614_870_000_000, "regularMarketPrice": 148.36})
    assert campos["market_cap"] == pytest.approx(614_870)


def test_preco_cai_para_previous_close_quando_mercado_fechado():
    assert umd.extrai_campos({"previousClose": 42.0})["preco_acao"] == 42.0


def test_booleano_nao_e_confundido_com_numero():
    assert umd._primeiro({"trailingPE": True}, "trailingPE") is None


# ---------------------------------------------------------------------------
# Validacao: faixas e variacao maxima
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "campo,valor,anterior",
    [
        ("preco_acao", 0.0, 148.36),          # zero disfarcado de preco
        ("market_cap", 12.0, 614_870),        # unidade errada (nao convertida)
        ("pe", 5_000.0, 24.98),               # fora de faixa
        ("dividend_yield_pct", 40.0, 2.78),   # fracao/percentual trocados
        ("ev_ebitda", -3.0, 11.68),           # negativo
    ],
)
def test_valores_absurdos_sao_rejeitados(campo, valor, anterior):
    ok, motivo = umd.valida(campo, valor, anterior)
    assert not ok and motivo


def test_variacao_grande_demais_e_rejeitada_como_possivel_split():
    ok, motivo = umd.valida("preco_acao", 74.18, 148.36)  # split 2:1
    assert not ok
    assert "split" in motivo


def test_variacao_normal_de_mercado_e_aceita():
    ok, _ = umd.valida("preco_acao", 152.90, 148.36)
    assert ok


def test_none_e_rejeitado_sem_motivo_de_alarme():
    ok, motivo = umd.valida("pe", None, 24.98)
    assert not ok and "ausente" in motivo


def test_nan_e_rejeitado():
    ok, _ = umd.valida("pe", float("nan"), 24.98)
    assert not ok


# ---------------------------------------------------------------------------
# Aplicacao: fail-safe
# ---------------------------------------------------------------------------
def _cotacao(**kwargs):
    base = {c: None for c in umd.ORDEM_MERCADO}
    base.update(kwargs)
    return base


def test_campo_invalido_mantem_valor_anterior(dados):
    antes = dados["empresas"][0]["mercado"]
    pe_novo = round(antes["pe"] * 1.02, 2)
    cot = {"XOM": _cotacao(preco_acao=0.0, pe=pe_novo)}
    finais, rel = umd.aplica_cotacoes(dados, cot)
    assert finais["XOM"]["preco_acao"] == antes["preco_acao"]   # preservado
    assert finais["XOM"]["pe"] == pe_novo                       # atualizado
    assert any(r["campo"] == "preco_acao" for r in rel.rejeicoes)


def test_ticker_sem_resposta_mantem_bloco_inteiro(dados):
    finais, rel = umd.aplica_cotacoes(dados, {})
    for empresa in dados["empresas"]:
        assert finais[empresa["ticker"]] == empresa["mercado"]
    assert len(rel.falhas) == len(dados["empresas"])
    assert rel.tickers_ok == []


def test_atualizacao_valida_e_registrada_com_variacao(dados):
    antes = dados["empresas"][1]["mercado"]["preco_acao"]
    depois = round(antes * 1.05, 2)
    _, rel = umd.aplica_cotacoes(dados, {"CVX": _cotacao(preco_acao=depois)})
    mudanca = next(m for m in rel.mudancas if m["ticker"] == "CVX")
    assert mudanca["antes"] == antes and mudanca["depois"] == depois
    assert mudanca["var_pct"] == pytest.approx(5.0, abs=0.05)


def test_valor_igual_ao_anterior_nao_conta_como_mudanca(dados):
    cot = {"XOM": _cotacao(preco_acao=dados["empresas"][0]["mercado"]["preco_acao"])}
    _, rel = umd.aplica_cotacoes(dados, cot)
    assert rel.mudancas == []
    assert "XOM" in rel.tickers_ok


def test_market_cap_e_arredondado_para_inteiro(dados):
    cot = {"XOM": _cotacao(market_cap=614_871.6)}
    finais, _ = umd.aplica_cotacoes(dados, cot)
    assert finais["XOM"]["market_cap"] == 614_872
    assert isinstance(finais["XOM"]["market_cap"], int)


# ---------------------------------------------------------------------------
# Reescrita cirurgica: o diff diario tem de ser pequeno e nao pode corromper nada
# ---------------------------------------------------------------------------
def test_reescrita_muda_so_a_linha_de_mercado(dados, bruto):
    finais, _ = umd.aplica_cotacoes(dados, {"XOM": _cotacao(preco_acao=150.0)})
    novo = umd.reescreve_json(bruto, finais)
    difs = [
        (a, b)
        for a, b in zip(bruto.splitlines(), novo.splitlines())
        if a != b
    ]
    assert len(difs) == 1
    assert '"mercado"' in difs[0][0]
    assert len(bruto.splitlines()) == len(novo.splitlines())


def test_reescrita_preserva_todos_os_dados_fundamentais(dados, bruto):
    cot = {e["ticker"]: _cotacao(preco_acao=e["mercado"]["preco_acao"] * 1.1) for e in dados["empresas"]}
    finais, _ = umd.aplica_cotacoes(dados, cot)
    novo = json.loads(umd.reescreve_json(bruto, finais))
    for antes, depois in zip(dados["empresas"], novo["empresas"]):
        assert antes["fy2025"] == depois["fy2025"]
        assert antes["q_recente"] == depois["q_recente"]
        assert antes["fontes"] == depois["fontes"]
        assert depois["mercado"]["preco_acao"] == round(antes["mercado"]["preco_acao"] * 1.1, 2)


def test_reescrita_continua_json_valido_e_com_as_7_empresas(dados, bruto):
    finais, _ = umd.aplica_cotacoes(dados, {"PBR": _cotacao(pe=6.10)})
    novo = json.loads(umd.reescreve_json(bruto, finais))
    assert len(novo["empresas"]) == 7
    assert novo["empresas"][-1]["mercado"]["pe"] == 6.10


def test_serializacao_reproduz_a_linha_original_byte_a_byte(dados, bruto):
    """Serializar um bloco sem alteracao tem de devolver o texto identico.

    E o que garante que uma atualizacao diaria mexa so nas empresas que
    mudaram de preco, e nao no arquivo inteiro.
    """
    originais = re.findall(r'"mercado": (\{[^{}]*\})', bruto)
    assert len(originais) == len(dados["empresas"])
    for empresa, texto in zip(dados["empresas"], originais):
        assert umd.serializa_mercado(empresa["mercado"]) == texto


def test_serializacao_nao_perde_chave_desconhecida():
    bloco = {"market_cap": 1000, "pe": 10.0, "ev_ebitda": 5.0, "dividend_yield_pct": 1.0,
             "preco_acao": 20.0, "campo_novo": "x"}
    assert '"campo_novo": "x"' in umd.serializa_mercado(bloco)


def test_datas_sao_sincronizadas(bruto):
    novo = umd.atualiza_datas(bruto, date(2026, 8, 3))
    assert '"atualizado_em": "2026-08-03"' in novo
    assert "snapshot' de mercado em 03/08/2026" in novo
    assert '"data_consulta": "2026-07-20"' in novo  # fundamentos nao se movem


def test_ordem_dos_tickers_e_respeitada_na_reescrita(dados, bruto):
    """Cada bloco tem de ir para a sua empresa -- nao pode haver deslocamento."""
    esperado = {
        e["ticker"]: round(e["mercado"]["pe"] + (i + 1) * 0.01, 2)
        for i, e in enumerate(dados["empresas"])
    }
    cot = {tk: _cotacao(pe=v) for tk, v in esperado.items()}
    finais, _ = umd.aplica_cotacoes(dados, cot)
    novo = json.loads(umd.reescreve_json(bruto, finais))
    for empresa in novo["empresas"]:
        assert empresa["mercado"]["pe"] == esperado[empresa["ticker"]]


def test_json_atualizado_continua_passando_no_build(dados, bruto, tmp_path):
    """A saida da rotina tem de ser digerivel por build_dashboard.py."""
    import build_dashboard as bd

    finais, _ = umd.aplica_cotacoes(dados, {"XOM": _cotacao(preco_acao=155.0, market_cap=642_000)})
    novo = json.loads(umd.reescreve_json(bruto, finais))
    enriquecido = bd.enriquecer(novo)
    xom = enriquecido["empresas"][0]
    # FCF yield usa o market cap novo: tem de ter acompanhado.
    esperado = xom["fy2025"]["fcf"] / 642_000 * 100
    assert xom["fy2025"]["derivados"]["fcf_yield_pct"] == pytest.approx(esperado, abs=0.01)


def test_formato_do_arquivo_vivo_suporta_escrita_cirurgica():
    """O arquivo VIVO precisa manter o bloco "mercado" em uma linha por empresa.

    Este e o unico teste que olha para indicadores_oleo_gas.json de verdade, e
    de proposito: ele nao afirma nada sobre os VALORES (que mudam a cada
    balanco), so sobre o FORMATO de que a escrita cirurgica depende. Foi esta
    garantia que pegou uma versao de update_fundamentals.py que reserializava o
    arquivo com indent=2 e trocava ~500 linhas de formatacao.
    """
    vivo = (RAIZ / "indicadores_oleo_gas.json").read_text(encoding="utf-8")
    finais = {
        "XOM": {"market_cap": 1, "pe": 1.0, "ev_ebitda": 1.0,
                "dividend_yield_pct": 1.0, "preco_acao": 1.0}
    }
    saida = umd.reescreve_json(vivo, finais)
    difs = [
        l for l in difflib.unified_diff(vivo.splitlines(), saida.splitlines(), lineterm="", n=0)
        if l.startswith(("-", "+")) and not l.startswith(("---", "+++"))
    ]
    # Uma linha removida e uma adicionada: so o bloco "mercado" do XOM.
    assert len(difs) == 2, f"formato do arquivo vivo mudou: {len(difs)} linhas afetadas"
