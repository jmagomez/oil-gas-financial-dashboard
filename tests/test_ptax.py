"""PTAX: media e fechamento por trimestre, e a recusa em converter com serie incompleta.

Nenhum teste toca a rede. O arquivo lido e o `ptax/raw.txt` de verdade.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

import ptax


@pytest.fixture(scope="module")
def cotacoes():
    return ptax.le()


def test_media_e_fechamento_do_2t26(cotacoes):
    t = ptax.taxas("2026-Q2", cotacoes)
    assert t["fechamento"] == 5.1766
    assert t["data_fechamento"] == "2026-06-30"
    assert t["media"] == pytest.approx(5.0494, abs=1e-4)
    assert t["dias_uteis"] == 61


def test_media_e_fechamento_sao_taxas_DIFERENTES(cotacoes):
    """A razao de existirem duas: no 2T26 elas distam 2,5%.

    Se fossem quase iguais, trocar uma pela outra seria detalhe. Nao sao.
    """
    t = ptax.taxas("2026-Q2", cotacoes)
    assert abs(t["fechamento"] / t["media"] - 1) > 0.02


def test_fechamento_aceita_ultimo_dia_util_antes_do_fim_do_trimestre(cotacoes):
    """31/12 nao tem PTAX: o fechamento do 4T25 e de 30/12."""
    assert ptax.taxas("2025-Q4", cotacoes)["data_fechamento"] == "2025-12-30"


def test_trimestre_sem_cotacao_nenhuma_e_recusado(cotacoes):
    with pytest.raises(ptax.PtaxIncompleta, match="sem nenhuma"):
        ptax.taxas("2031-Q1", cotacoes)


def test_trimestre_pela_metade_e_recusado(cotacoes):
    """Media de meio trimestre e um numero plausivel -- e errado."""
    metade = {d: v for d, v in cotacoes.items() if not (d.year == 2026 and d.month in (5, 6))}
    with pytest.raises(ptax.PtaxIncompleta, match="dias uteis"):
        ptax.taxas("2026-Q2", metade)


def test_fechamento_que_nao_e_do_fim_do_trimestre_e_recusado(cotacoes):
    """Com dias suficientes mas sem a ultima semana, o 'fechamento' seria outro dia."""
    sem_fim = {d: v for d, v in cotacoes.items() if not (date(2026, 6, 24) <= d <= date(2026, 6, 30))}
    assert ptax.por_trimestre(sem_fim)["2026-Q2"]["dias_uteis"] >= ptax.MIN_DIAS_UTEIS
    with pytest.raises(ptax.PtaxIncompleta, match="dias do fim"):
        ptax.taxas("2026-Q2", sem_fim)


def test_fim_do_trimestre():
    assert ptax.fim_do_trimestre("2026-Q3") == date(2026, 9, 30)
    assert ptax.fim_do_trimestre("2025-Q4") == date(2025, 12, 31)
    assert ptax.fim_do_trimestre("2024-Q1") == date(2024, 3, 31)


# ---------------------------------------------------------------------------
# Resposta da API e escrita no arquivo
# ---------------------------------------------------------------------------
RESPOSTA = json.dumps({
    "value": [
        {"cotacaoVenda": 5.4321, "dataHoraCotacao": "2026-07-01 13:09:28.318"},
        {"cotacaoVenda": 5.44, "dataHoraCotacao": "2026-07-02 13:04:11.1"},
    ]
})


def test_interpreta_a_resposta_do_banco_central():
    assert ptax.interpreta_resposta(RESPOSTA) == {date(2026, 7, 1): 5.4321, date(2026, 7, 2): 5.44}


def test_cotacao_fora_de_faixa_na_resposta_e_erro():
    ruim = json.dumps({"value": [{"cotacaoVenda": 54321.0, "dataHoraCotacao": "2026-07-01 13:00:00"}]})
    with pytest.raises(ValueError, match="fora da faixa"):
        ptax.interpreta_resposta(ruim)


def test_acrescenta_so_os_dias_novos_no_formato_do_arquivo(tmp_path):
    arq = tmp_path / "raw.txt"
    arq.write_text("29/06/2026;5,1717\n30/06/2026;5,1766\n", encoding="utf-8")
    novas = {date(2026, 6, 30): 5.1766, date(2026, 7, 1): 5.4321, date(2026, 7, 2): 5.44}
    assert ptax.acrescenta(novas, arq) == 2
    assert arq.read_text(encoding="utf-8") == (
        "29/06/2026;5,1717\n30/06/2026;5,1766\n01/07/2026;5,4321\n02/07/2026;5,4400\n"
    )
    # idempotente: rodar de novo nao duplica nada
    assert ptax.acrescenta(novas, arq) == 0


def test_dia_ja_gravado_com_valor_diferente_para_tudo(tmp_path):
    """PTAX de dia fechado nao muda. Se mudou, alguem tem de olhar."""
    arq = tmp_path / "raw.txt"
    arq.write_text("30/06/2026;5,1766\n", encoding="utf-8")
    with pytest.raises(ValueError, match="diverge"):
        ptax.acrescenta({date(2026, 6, 30): 5.2}, arq)
    assert arq.read_text(encoding="utf-8") == "30/06/2026;5,1766\n"


def test_linha_ilegivel_no_arquivo_e_erro(tmp_path):
    arq = tmp_path / "raw.txt"
    arq.write_text("30/06/2026;5,1766\nlixo\n", encoding="utf-8")
    with pytest.raises(ValueError, match="linha 2"):
        ptax.le(arq)
