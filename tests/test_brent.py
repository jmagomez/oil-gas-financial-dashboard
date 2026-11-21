"""Brent medio por periodo, da serie mensal da EIA versionada em brent/raw.txt."""

from __future__ import annotations

import pytest

import brent

SERIE = {"2026-07": 83.76, "2026-08": 91.08, "2026-09": 114.16}


def test_trimestre_e_a_media_dos_tres_meses_nos_dois_formatos_de_rotulo():
    assert brent.media_trimestre("Q3 2026", SERIE) == pytest.approx((83.76 + 91.08 + 114.16) / 3, abs=0.01)
    assert brent.media_trimestre("2026-Q3", SERIE) == brent.media_trimestre("Q3 2026", SERIE)


def test_mes_faltando_nao_vira_media_de_pedaco():
    assert brent.media_trimestre("Q3 2026", {"2026-07": 83.76, "2026-08": 91.08}) is None
    assert brent.media_ano(2026, SERIE) is None


def test_rotulo_invalido_devolve_none():
    assert brent.media_trimestre("FY2025", SERIE) is None


@pytest.mark.parametrize("trimestre,bp", [("Q3 2026", 96.99), ("Q2 2026", 103.85), ("Q3 2025", 69.13)])
def test_serie_versionada_confere_com_o_brent_que_a_bp_divulga(trimestre, bp):
    """Ancora externa: tabela de precos de referencia do release do 3T26 da BP (Dated Brent).

    A EIA e a BP usam avaliacoes diferentes do mesmo petroleo; a diferenca fica
    abaixo de 1%. Mais que isso, a serie versionada esta errada.
    """
    assert brent.media_trimestre(trimestre) == pytest.approx(bp, rel=0.01)


def test_mescla_acrescenta_sem_reescrever_e_rejeita_fora_de_faixa():
    nova, rejeitados = brent.mescla(
        {"2026-09": 114.16},
        [{"period": "2026-09", "value": "1.00"},     # existente: nao reescreve
         {"period": "2026-10", "value": "123.93"},
         {"period": "2026-11", "value": "12393"}],   # unidade errada
    )
    assert nova == {"2026-09": 114.16, "2026-10": 123.93}
    assert rejeitados == ["2026-11=12393.0"]


def test_grava_e_le_ida_e_volta(tmp_path):
    arq = tmp_path / "raw.txt"
    brent.grava({"2026-10": 123.93, "2026-09": 114.16}, arq)
    assert arq.read_text(encoding="utf-8") == "2026-09;114.16\n2026-10;123.93\n"
    assert brent.le(arq) == {"2026-09": 114.16, "2026-10": 123.93}
