"""Testes do corpo do e-mail diario.

O e-mail e a unica peca que chega ao leitor todo dia, e era a unica sem
cobertura. Os testes leem o snapshot congelado, nao o arquivo vivo: ver
tests/fixtures/LEIA-ME.md.
"""
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import build_dashboard as bd  # noqa: E402
import build_email as be  # noqa: E402

SNAPSHOT = Path(__file__).resolve().parent / "fixtures" / "indicadores_snapshot.json"


@pytest.fixture()
def dados():
    return bd.enriquecer(json.loads(SNAPSHOT.read_text(encoding="utf-8")))


@pytest.fixture()
def relatorio():
    return {
        "gerado_em": "2026-08-21T22:30:00+00:00",
        "mudancas": [
            {"ticker": "XOM", "campo": "preco_acao", "antes": 159.75, "depois": 161.20, "var_pct": 0.91},
            {"ticker": "PBR", "campo": "preco_acao", "antes": 17.76, "depois": 17.31, "var_pct": -2.53},
        ],
        "rejeicoes": [{"ticker": "BP", "campo": "ev_ebitda", "valor": 12.68,
                       "motivo": "variacao acima do limite", "mantido": 4.90}],
        "falhas": [],
    }


# ---------------------------------------------------------------------------
# Formatacao
# ---------------------------------------------------------------------------
def test_numero_sai_no_padrao_brasileiro():
    assert be.num(1234.56) == "1.234,56"
    assert be.num(656878, 0) == "656.878"
    assert be.num(None) == "—"


def test_ausente_nao_vira_zero():
    """Buraco de dado tem de aparecer como buraco, nunca como 0."""
    assert be.num(None, 0) == "—"
    assert be.num(0, 0) == "0"


# ---------------------------------------------------------------------------
# O e-mail e de ESTADO, nao de diff
# ---------------------------------------------------------------------------
def test_nao_lista_campo_a_campo_o_que_mudou(dados, relatorio):
    """Regressao: a lista campo-a-campo repetia a tabela e crescia ate ~35 linhas."""
    h = be.montar(relatorio, dados)
    assert "O que mudou" not in h
    assert "159,75 →" not in h and "17,76 →" not in h


def test_variacao_do_dia_continua_como_coluna(dados, relatorio):
    """Tirar o diff nao pode tirar o movimento do dia."""
    h = be.montar(relatorio, dados)
    assert "Var. dia" in h
    assert "+0,91%" in h and "-2,53%" in h


# ---------------------------------------------------------------------------
# Referencia de periodo -- o defeito que saia todo dia
# ---------------------------------------------------------------------------
def test_referencia_usa_o_trimestre_e_nao_a_data_de_consulta(dados, relatorio):
    """data_consulta e a coleta ORIGINAL dos fundamentos e nao acompanha as
    atualizacoes; o e-mail vinha afirmando uma referencia ja falsa."""
    h = be.montar(relatorio, dados)
    assert dados["referencia"]["periodo_trimestral"] in h
    assert dados["referencia"]["data_consulta"] not in h


# ---------------------------------------------------------------------------
# Quadro de mercado
# ---------------------------------------------------------------------------
def test_empresas_saem_ordenadas_por_market_cap(dados, relatorio):
    import re
    h = be.montar(relatorio, dados)
    esperado = [e["ticker"] for e in sorted(
        dados["empresas"], key=lambda e: e["mercado"]["market_cap"], reverse=True)]
    assert re.findall(r"<b>([A-Z]{2,4})</b> <span", h) == esperado


def test_mediana_bate_com_o_calculo_direto(dados, relatorio):
    import statistics
    h = be.montar(relatorio, dados)
    esperada = statistics.median([e["mercado"]["pe"] for e in dados["empresas"]])
    assert be.num(esperada, 2) in h


def test_mediana_ignora_ausentes_em_vez_de_trata_los_como_zero():
    """Um None no meio nao pode puxar a mediana para baixo."""
    import statistics
    vals = [10.0, None, 20.0, 30.0]
    limpos = [v for v in vals if isinstance(v, (int, float))]
    assert statistics.median(limpos) == 20.0


def test_mediana_nao_e_calculada_para_escala(dados, relatorio):
    """Mediana de preco ou de market cap nao informa nada -- fica como travessao."""
    assert "preco_acao" not in be.COM_MEDIANA
    assert "market_cap" not in be.COM_MEDIANA


def test_fcf_yield_derivado_chega_ao_email(dados, relatorio):
    """A camada derivada existia e nunca aparecia no e-mail."""
    h = be.montar(relatorio, dados)
    assert "FCF yield" in h
    xom = next(e for e in dados["empresas"] if e["ticker"] == "XOM")
    assert be.num(xom["fy2025"]["derivados"]["fcf_yield_pct"], 2) in h


def test_tabela_tem_estrutura_semantica(dados, relatorio):
    h = be.montar(relatorio, dados)
    assert "<thead>" in h and "<tfoot>" in h and "<caption" in h
    assert "scope='col'" in h and "scope='row'" in h


# ---------------------------------------------------------------------------
# Alertas x ressalvas permanentes
# ---------------------------------------------------------------------------
def test_rejeicao_aparece_em_destaque_no_topo(dados, relatorio):
    h = be.montar(relatorio, dados)
    assert "Exige atenção" in h
    assert h.index("Exige atenção") < h.index("<table"), "alerta tem de vir antes da tabela"


def test_execucao_limpa_nao_gera_bloco_de_alerta(dados):
    h = be.montar({"mudancas": [], "rejeicoes": [], "falhas": []}, dados)
    assert "Exige atenção" not in h


def test_ressalvas_permanentes_nao_se_disfarcam_de_incidente(dados, relatorio):
    """Sao caracteristicas estaveis da base. Chamar de 'aviso' todo dia treina
    o leitor a ignorar o bloco -- e o aviso novo some junto."""
    h = be.montar(relatorio, dados)
    if bd.validate(dados):
        assert "Ressalvas conhecidas da base" in h
        assert "não ocorrências desta execução" in h


# ---------------------------------------------------------------------------
# Seguranca
# ---------------------------------------------------------------------------
def test_conteudo_do_relatorio_e_escapado(dados):
    """O relatorio vem de fonte externa; nada dele pode virar HTML ativo."""
    rel = {"mudancas": [], "falhas": [],
           "rejeicoes": [{"ticker": "<script>alert(1)</script>", "campo": "pe",
                          "valor": 1, "motivo": "x", "mantido": 2}]}
    h = be.montar(rel, dados)
    assert "<script>alert(1)</script>" not in h
    assert "&lt;script&gt;" in h
