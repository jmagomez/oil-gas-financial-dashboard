"""Testes das primitivas compartilhadas de escrita cirúrgica.

update_market_data.py e update_fundamentals.py têm cada um sua própria
suíte, exercitando estas primitivas através da API pública dos dois módulos
(serializa_mercado, serializa_bloco, reescreve_json, atualiza_datas,
atualiza_referencia). Este arquivo testa o módulo compartilhado diretamente,
sem depender de nenhum dos dois regimes de dado.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import escrita_cirurgica as ec  # noqa: E402


# ---------------------------------------------------------------------------
# posicoes_dos_tickers
# ---------------------------------------------------------------------------
def test_encontra_cada_ticker_na_ordem_do_arquivo():
    texto = '{"ticker": "XOM"}\n{"ticker": "CVX"}\n'
    posicoes = ec.posicoes_dos_tickers(texto)
    assert [t for t, _ in posicoes] == ["XOM", "CVX"]


def test_sem_ticker_no_texto_levanta_valueerror():
    try:
        ec.posicoes_dos_tickers("{}")
    except ValueError as exc:
        assert "ticker" in str(exc)
    else:
        raise AssertionError("deveria ter levantado ValueError")


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
