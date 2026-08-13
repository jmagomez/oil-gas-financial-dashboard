"""Barra regressao da camada de acessibilidade.

Os graficos sao <canvas>: sem esta camada eles ficam invisiveis para leitor de
tela. build_dashboard.py so avisa se os assets sumirem -- quem falha e aqui.

O teste injeta num HTML minimo em vez de ler o dashboard_oleo_gas.html
commitado: o HTML e um artefato regenerado por build-dashboard.yml depois do
push, entao depender dele criaria uma corrida em que o CI testa a versao antiga.
"""
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import build_dashboard as bd  # noqa: E402

STUB = "<html><head><style>a{}</style></head><body><p>x</p></body></html>"


def test_assets_de_acessibilidade_existem():
    assert bd.A11Y_CSS_PATH.exists(), "assets_a11y.css ausente"
    assert bd.A11Y_JS_PATH.exists(), "assets_a11y.js ausente"


def test_camada_e_injetada():
    h = bd._injeta_camada_acessibilidade(STUB)
    assert ".sr-only{" in h, "CSS da camada ausente"
    assert "id: 'acessibilidade'" in h, "plugin Chart.js ausente"
    assert h.index(".sr-only{") < h.index("</style>"), "CSS fora do <style>"
    assert h.index("id: 'acessibilidade'") < h.index("</body>"), "JS fora do <body>"


def test_usa_afterUpdate_e_nao_afterRender():
    # afterRender dispara a cada frame da animacao (~33x por grafico) e
    # reconstruir a tabela equivalente a cada frame trava a thread principal.
    js = bd.A11Y_JS_PATH.read_text(encoding="utf-8")
    assert "afterUpdate: function(chart)" in js
    assert "afterRender: function(chart)" not in js


@pytest.mark.parametrize("marcador", [
    "role','img'", "aria-live", "prefers-reduced-motion", "skip-link", "aria-sort",
])
def test_recursos_de_acessibilidade_presentes(marcador):
    assert marcador in bd._injeta_camada_acessibilidade(STUB), f"faltando: {marcador}"


def test_build_nao_quebra_sem_os_assets(monkeypatch, tmp_path):
    # Regressao: o build nao pode derrubar a regeneracao do dashboard so
    # porque um asset sumiu -- quem reclama e este arquivo de teste.
    monkeypatch.setattr(bd, "A11Y_CSS_PATH", tmp_path / "nao_existe.css")
    assert bd._injeta_camada_acessibilidade(STUB) == STUB
