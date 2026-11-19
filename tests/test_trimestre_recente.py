"""O "trimestre mais recente" e derivado das empresas, nunca de um rotulo unico.

Ver `build_dashboard.trimestres_recentes` para o historico do defeito.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import build_dashboard as bd

ROOT = Path(__file__).resolve().parents[1]


def _empresas(*pares):
    return [{"ticker": t, "q_recente": {"trimestre": q}} for t, q in pares]


def test_uniforme_quando_todas_estao_no_mesmo_trimestre():
    tr = bd.trimestres_recentes(_empresas(("XOM", "Q3 2026"), ("PBR", "Q3 2026")))
    assert tr["uniforme"] is True
    assert tr["distintos"] == ["Q3 2026"]
    assert bd.descreve_trimestres(tr) == "Q3 2026"


def test_misto_nao_afirma_trimestre_unico_e_diz_quem_esta_onde():
    tr = bd.trimestres_recentes(
        _empresas(("XOM", "Q4 2026"), ("CVX", "Q4 2026"), ("SHEL", "Q3 2026"), ("PBR", "Q3 2026"))
    )
    assert tr["uniforme"] is False
    assert tr["empresas_por_trimestre"] == {"Q3 2026": ["PBR", "SHEL"], "Q4 2026": ["CVX", "XOM"]}
    texto = bd.descreve_trimestres(tr)
    assert texto == "trimestre mais recente de cada empresa: Q4 2026 (CVX, XOM); Q3 2026 (PBR, SHEL)"


def test_ordem_e_cronologica_e_nao_alfabetica():
    """Na virada do ano a ordem de texto inverte: "Q1 2027" < "Q4 2026"."""
    tr = bd.trimestres_recentes(_empresas(("XOM", "Q1 2027"), ("PBR", "Q4 2026")))
    assert sorted(["Q1 2027", "Q4 2026"]) == ["Q1 2027", "Q4 2026"]  # a armadilha
    assert tr["distintos"] == ["Q4 2026", "Q1 2027"]
    assert tr["mais_recente"] == "Q1 2027"


def test_rotulo_fora_do_formato_e_erro_e_nao_ordem_silenciosa():
    with pytest.raises(ValueError):
        bd.ordem_trimestre("3T26")


def test_payload_publicado_carrega_a_derivacao():
    dados = json.loads((ROOT / "dashboard_data.json").read_text(encoding="utf-8"))
    tr = dados["meta_build"]["trimestre_recente"]
    assert tr["por_empresa"] == {e["ticker"]: e["q_recente"]["trimestre"] for e in dados["empresas"]}


def test_build_avisa_quando_a_coluna_do_trimestre_mistura_periodos():
    raw = json.loads((ROOT / "indicadores_oleo_gas.json").read_text(encoding="utf-8"))
    raw["empresas"][0]["q_recente"]["trimestre"] = "Q4 2026"
    problemas = bd.validate(bd.enriquecer(raw))
    assert any("trimestres diferentes" in p for p in problemas)


# ---------------------------------------------------------------------------
# Contratos: as duas fontes erradas nao podem voltar
# ---------------------------------------------------------------------------
def test_arquivo_vivo_nao_armazena_mais_um_trimestre_para_o_conjunto():
    raw = json.loads((ROOT / "indicadores_oleo_gas.json").read_text(encoding="utf-8"))
    assert "periodo_trimestral" not in raw["referencia"]


def test_template_nao_toma_o_trimestre_de_uma_empresa_pelo_do_conjunto():
    """`empresas[0].q_recente.trimestre` era o trimestre da XOM, so por ela ser a primeira."""
    t = (ROOT / "dashboard_template.html").read_text(encoding="utf-8")
    assert not re.search(r"empresas\[\d+\]\.q_recente\.trimestre", t)
    assert "periodo_trimestral" not in t
    assert "meta_build.trimestre_recente" in t


def test_csv_exportado_rotula_cada_linha_com_o_trimestre_da_propria_empresa():
    """A exportacao e a saida que mais circula fora do dashboard -- sem o aviso visual ao lado."""
    t = (ROOT / "dashboard_template.html").read_text(encoding="utf-8")
    corpo = t[t.index("function baixarCsv(){"):t.index("function baixarCsv(){") + 900]
    assert "periodoDaLinha(e)" in corpo
