"""Testes da escrita cirúrgica de update_fundamentals.py no JSON primário.

Separado de test_update_fundamentals.py (que exige pandas para montar os
DataFrames fabricados da coleta — ver o comentario em seu topo) porque nada
aqui precisa de pandas: reescreve_json, serializa_bloco, serializa_historico
e atualiza_referencia sao manipulacao pura de dict e de texto. Se pandas
estiver ausente do ambiente, este arquivo continua rodando e cobrindo o
caminho de escrita, em vez de ser pulado junto com os ~41 testes de coleta.

Mesma motivacao do equivalente em test_update_market.py: o diff de um
trimestre novo tem de ficar pequeno e nao pode corromper o resto do
arquivo. O proprio docstring de update_fundamentals.reescreve_json conta que
uma versao anterior reserializava o JSON inteiro e trocava ~500 linhas de
formatacao — essa classe de regressao tinha teste para o regime de mercado
(test_update_market.test_formato_do_arquivo_vivo_suporta_escrita_cirurgica)
mas nao para o de fundamentos. E a lacuna que este arquivo fecha.
"""

from __future__ import annotations

import difflib
import json
import sys
from datetime import date
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import update_fundamentals as uf  # noqa: E402

SNAPSHOT = RAIZ / "tests" / "fixtures" / "indicadores_snapshot.json"

# Numeros reais do 2T26 da ExxonMobil (mesma fixture de test_update_fundamentals.py),
# usados aqui so para montar um trimestre "novo" plausivel e passar as checagens
# de coerencia -- nao ha assercao de valor neste arquivo, so de formato.
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


@pytest.fixture()
def dados():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


@pytest.fixture()
def bruto():
    return SNAPSHOT.read_text(encoding="utf-8")


def _coletado_xom_q2():
    """Um trimestre novo (Q2 2026) para a XOM, que ja esta em Q1 2026 no snapshot."""
    return {
        "XOM": {
            "fim": date(2026, 6, 30),
            "linhas": dict(XOM_Q2_2026),
            "ttm": {"lucro_liquido": 32_781},
            "anteriores": [],
        }
    }


def _trimestre_seguinte(trimestre_atual: str) -> str:
    ano, tri = uf.ordem_trimestre(trimestre_atual)
    return f"Q1 {ano + 1}" if tri == 4 else f"Q{tri + 1} {ano}"


def _coletado_proximo_trimestre(ticker: str, trimestre_atual: str):
    """Um trimestre plausivel, um a frente do que `ticker` tem hoje.

    Os valores vem de XOM_Q2_2026 (numeros reais, so para passar as checagens
    de coerencia) — o que varia aqui e a DATA, nao a magnitude: este teste e
    sobre formato, nao sobre o numero em si.
    """
    fim = uf.fim_do_trimestre(_trimestre_seguinte(trimestre_atual))
    return {
        ticker: {
            "fim": fim,
            "linhas": dict(XOM_Q2_2026),
            "ttm": {"lucro_liquido": 32_781},
            "anteriores": [],
        }
    }


# ---------------------------------------------------------------------------
# serializa_bloco / serializa_historico — formato de uma linha
# ---------------------------------------------------------------------------
# Ao contrario de update_market_data.reescreve_json (que reescreve o bloco
# "mercado" de TODAS as empresas a cada execucao, tocadas ou nao, por isso
# precisa reproduzir byte a byte um valor nao modificado), este reescreve so
# os tickers em `tickers_novos` — uma empresa sem trimestre novo nunca passa
# por serializa_bloco. Por isso nao ha aqui um teste de "round-trip byte a
# byte do dado nao tocado": essa garantia nao existe por desenho, e um campo
# como divida_patrimonio_pct, que no arquivo vivo aparece tanto como "18.3"
# quanto como "24" (sem decimal), nao tem um formato fixo para preservar.
def test_serializa_bloco_respeita_a_ordem_canonica(dados):
    bloco = uf.serializa_bloco(dados["empresas"][0]["q_recente"], uf.CAMPOS_TRIMESTRE)
    chaves = [m.split(":")[0].strip().strip('"') for m in bloco.strip("{}").split(", ")]
    assert chaves == [c for c in uf.CAMPOS_TRIMESTRE if c in dados["empresas"][0]["q_recente"]]


def test_serializa_historico_vazio():
    assert uf.serializa_historico([], recuo="  ") == "[]"


def test_serializa_historico_um_item_por_linha():
    itens = [
        {"periodo": "2025-Q4", "receita": 100},
        {"periodo": "2026-Q1", "receita": 110},
    ]
    saida = uf.serializa_historico(itens, recuo="  ")
    linhas = saida.splitlines()
    assert linhas[0] == "["
    assert linhas[-1] == "  ]"
    assert len(linhas) == 2 + len(itens)  # abre + N itens + fecha


# ---------------------------------------------------------------------------
# reescreve_json — so o ticker que mudou, resto intocado
# ---------------------------------------------------------------------------
def test_reescrita_toca_so_o_ticker_com_trimestre_novo(dados, bruto):
    saida, rel = uf.aplica_fundamentos(dados, _coletado_xom_q2())
    assert {n["ticker"] for n in rel.novos} == {"XOM"}

    novo_texto = uf.reescreve_json(bruto, saida, {"XOM"}, date(2026, 10, 18))
    novo = json.loads(novo_texto)

    for antes, depois in zip(dados["empresas"], novo["empresas"], strict=True):
        if antes["ticker"] == "XOM":
            continue
        # Nenhuma empresa alem da XOM pode ter qualquer bloco alterado.
        assert antes == depois


def test_reescrita_promove_q_recente_para_o_historico(dados, bruto):
    saida, _ = uf.aplica_fundamentos(dados, _coletado_xom_q2())
    novo = json.loads(uf.reescreve_json(bruto, saida, {"XOM"}, date(2026, 10, 18)))
    xom = next(e for e in novo["empresas"] if e["ticker"] == "XOM")

    assert xom["q_recente"]["trimestre"] == "Q2 2026"
    # O Q1 2026 que estava em q_recente foi arquivado no historico.
    assert [h["periodo"] for h in xom["historico"]] == ["2026-Q1"]
    assert xom["historico"][0]["receita"] == dados["empresas"][0]["q_recente"]["receita"]


def test_reescrita_continua_json_valido_e_com_as_7_empresas(dados, bruto):
    saida, _ = uf.aplica_fundamentos(dados, _coletado_xom_q2())
    novo = json.loads(uf.reescreve_json(bruto, saida, {"XOM"}, date(2026, 10, 18)))
    assert len(novo["empresas"]) == len(dados["empresas"])
    assert [e["ticker"] for e in novo["empresas"]] == [e["ticker"] for e in dados["empresas"]]


def test_reescrita_sincroniza_referencia_quando_um_so_trimestre(dados, bruto):
    saida, _ = uf.aplica_fundamentos(dados, _coletado_xom_q2())
    novo_texto = uf.reescreve_json(bruto, saida, {"XOM"}, date(2026, 10, 18))
    assert '"atualizado_em": "2026-10-18"' in novo_texto
    assert "Q2 2026 (trimestre encerrado em 30/06/2026)" in novo_texto


def test_reescrita_sem_tickers_novos_nao_toca_referencia(dados, bruto):
    """tickers_novos vazio: nada a promover, nada a sincronizar."""
    igual = uf.reescreve_json(bruto, dados, set(), date(2026, 10, 18))
    assert igual == bruto


# ---------------------------------------------------------------------------
# A garantia central: o diff de um trimestre novo tem de ser pequeno
# ---------------------------------------------------------------------------
def test_formato_do_arquivo_vivo_suporta_escrita_cirurgica_em_fundamentos():
    """Mesma garantia de test_update_market, para o regime de fundamentos.

    Roda contra indicadores_oleo_gas.json de VERDADE — nao o snapshot — e nao
    afirma nada sobre valores, so sobre quantas linhas uma promocao de
    trimestre pode tocar. Promover a XOM para um trimestre novo deve mudar
    exatamente: a linha de q_recente, o bloco de historico (uma linha nova,
    ja que o item que sai de q_recente e so anexado ao fim) e, quando houver
    bloco de proveniencia, essa linha — nunca a formatacao de outra empresa
    nem a estrutura do arquivo inteiro.
    """
    vivo = (RAIZ / "indicadores_oleo_gas.json").read_text(encoding="utf-8")
    dados_vivos = json.loads(vivo)
    xom_atual = next(e for e in dados_vivos["empresas"] if e["ticker"] == "XOM")

    coletado = _coletado_proximo_trimestre("XOM", xom_atual["q_recente"]["trimestre"])
    saida, rel = uf.aplica_fundamentos(dados_vivos, coletado)
    assert {n["ticker"] for n in rel.novos} == {"XOM"}, rel.resumo()

    nova = uf.reescreve_json(vivo, saida, {"XOM"}, date(2026, 10, 18))
    difs = [
        linha
        for linha in difflib.unified_diff(vivo.splitlines(), nova.splitlines(), lineterm="", n=0)
        if linha.startswith(("-", "+")) and not linha.startswith(("---", "+++"))
    ]
    # Composicao esperada do diff, sempre a mesma por desenho, independente de
    # quantos periodos ja existam no historico: "referencia" no topo do
    # arquivo (periodo_trimestral + atualizado_em, 2 linhas cada = 4),
    # q_recente (1+1 = 2), historico (a ultima linha existente ganha uma
    # virgula -- 1 removida, 1 adicionada -- e o periodo novo entra como mais
    # 1 linha = 3) e proveniencia, se existir (1+1 = 2). Total: 11. A margem
    # ate 14 absorve um ticker sem proveniencia anterior (vira so +1, sem
    # remover) sem tornar o teste fragil a esse detalhe.
    assert len(difs) <= 14, (
        f"escrita cirurgica tocou {len(difs)} linhas — bem mais que as ~11 esperadas "
        "para promover um unico trimestre; suspeite de reserializacao do arquivo inteiro"
    )

    outros_tickers = {e["ticker"] for e in dados_vivos["empresas"] if e["ticker"] != "XOM"}
    for linha in difs:
        for ticker in outros_tickers:
            assert f'"{ticker}"' not in linha, f"diff tocou dados de {ticker}: {linha!r}"
