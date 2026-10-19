"""Testes das primitivas compartilhadas de escrita cirúrgica.

update_market_data.py e update_fundamentals.py têm cada um sua própria
suíte, exercitando estas primitivas através da API pública dos dois módulos
(serializa_mercado, serializa_bloco, reescreve_json, atualiza_datas,
atualiza_referencia). Este arquivo testa o módulo compartilhado diretamente,
sem depender de nenhum dos dois regimes de dado.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

import escrita_cirurgica as ec  # noqa: E402


# ---------------------------------------------------------------------------
# posicoes_dos_tickers
# ---------------------------------------------------------------------------
def _doc(referencia: str = "", empresas: str = '{"ticker": "XOM"}, {"ticker": "CVX"}') -> str:
    """Documento mínimo com a mesma forma do arquivo vivo.

    A primitiva confere o texto contra a estrutura, então precisa de um JSON de
    verdade — é essa conferência que impede o pareamento deslocado.
    """
    return '{\n  "referencia": {' + referencia + '},\n  "empresas": [' + empresas + "]\n}"


def test_encontra_cada_ticker_na_ordem_do_arquivo():
    posicoes = ec.posicoes_dos_tickers(_doc())
    assert [t for t, _ in posicoes] == ["XOM", "CVX"]


def test_sem_ticker_no_texto_levanta_valueerror():
    try:
        ec.posicoes_dos_tickers(_doc(empresas=""))
    except ValueError as exc:
        assert "ticker" in str(exc)
    else:
        raise AssertionError("deveria ter levantado ValueError")


def test_sem_chave_empresas_levanta_valueerror():
    try:
        ec.posicoes_dos_tickers('{"referencia": {"ticker": "XOM"}}')
    except ValueError as exc:
        assert "empresas" in str(exc)
    else:
        raise AssertionError("deveria ter levantado ValueError")


def test_ticker_em_referencia_nao_desloca_o_pareamento():
    """Regressão: a busca varria o arquivo inteiro.

    Qualquer chave "ticker" em `referencia` — um registro de exceções, um mapa
    de ADS, uma nota estruturada — entrava na lista ANTES das empresas e
    deslocava tudo: cada empresa passava a receber o bloco da seguinte. Não
    quebrava nada visível (JSON válido, nenhum campo sumia), só trocava os
    números entre companhias.
    """
    posicoes = ec.posicoes_dos_tickers(_doc(referencia='"pendencias": [{"ticker": "BP"}]'))
    assert [t for t, _ in posicoes] == ["XOM", "CVX"]


def test_ticker_extra_dentro_de_uma_empresa_e_recusado():
    """O recorte em "empresas" sozinho não pega este caso — a conferência pega."""
    texto = _doc(empresas='{"ticker": "XOM", "nome": "x"}, {"ticker": "CVX"}')
    texto = texto.replace('"nome": "x"', '"ticker": "XOM"', 1)
    try:
        ec.posicoes_dos_tickers(texto)
    except ValueError as exc:
        assert "deslocado" in str(exc)
    else:
        raise AssertionError("pareamento deslocado deveria ter sido recusado")


def test_arquivo_vivo_passa_na_conferencia():
    vivo = (RAIZ / "indicadores_oleo_gas.json").read_text(encoding="utf-8")
    assert len(ec.posicoes_dos_tickers(vivo)) == len(json.loads(vivo)["empresas"])


# ---------------------------------------------------------------------------
# serializa_bloco_canonico
# ---------------------------------------------------------------------------
def test_respeita_a_ordem_canonica_e_ignora_chave_ausente():
    bloco = {"b": 2, "a": 1}
    assert ec.serializa_bloco_canonico(bloco, ["a", "b", "c"]) == '{"a": 1, "b": 2}'


def test_chave_extra_vai_para_o_fim_na_ordem_do_dict():
    bloco = {"a": 1, "z": 9, "b": 2}
    saida = ec.serializa_bloco_canonico(bloco, ["a", "b"])
    assert saida == '{"a": 1, "b": 2, "z": 9}'


def test_formata_custom_so_vale_para_chaves_canonicas():
    """Uma chave extra de tipo inesperado (ex.: string num bloco numerico) nao
    pode quebrar so porque o `formata` do chamador assume float."""

    def formata_float(_chave, v):
        return f"{float(v):.2f}"

    bloco = {"a": 1, "extra": "texto"}
    saida = ec.serializa_bloco_canonico(bloco, ["a"], formata=formata_float)
    assert saida == '{"a": 1.00, "extra": "texto"}'


def test_sem_formata_usa_json_dumps_puro():
    bloco = {"a": True, "b": None, "c": "x"}
    assert ec.serializa_bloco_canonico(bloco, ["a", "b", "c"]) == '{"a": true, "b": null, "c": "x"}'


# ---------------------------------------------------------------------------
# atualiza_campo_data
# ---------------------------------------------------------------------------
def test_atualiza_campo_data_troca_so_a_data():
    bruto = '"referencia": {"atualizado_em": "2026-01-01", "outro_campo": "intacto"}'
    novo = ec.atualiza_campo_data(bruto, date(2026, 10, 18))
    assert '"atualizado_em": "2026-10-18"' in novo
    assert '"outro_campo": "intacto"' in novo


def test_atualiza_campo_data_sem_o_campo_nao_muda_nada():
    bruto = '{"outro": 1}'
    assert ec.atualiza_campo_data(bruto, date(2026, 10, 18)) == bruto
