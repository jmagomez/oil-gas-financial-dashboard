"""O registro METRICAS do template tem que casar com o payload do build.

Esta lacuna deixou passar um defeito real: um campo derivado foi removido de
`build_dashboard.py` e a entrada correspondente ficou no template, apontando
para `p.derivados.<campo>` inexistente. A suite inteira passou -- 193 testes --
e o dashboard publicado exibiu uma coluna de travessoes para as sete empresas.

Nenhum teste olhava para os dois lados ao mesmo tempo: os de build conferem o
payload, os de a11y conferem a injecao, e o contrato entre o template e o
payload nao era de ninguem.
"""
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

import build_dashboard as bd  # noqa: E402


@pytest.fixture(scope="module")
def payload():
    raw = json.loads((ROOT / "indicadores_oleo_gas.json").read_text(encoding="utf-8"))
    return bd.enriquecer(raw)


@pytest.fixture(scope="module")
def metricas():
    """Extrai de METRICAS o nome de cada indicador e o caminho que ele le."""
    texto = (ROOT / "dashboard_template.html").read_text(encoding="utf-8")
    ini = texto.index("const METRICAS = {")
    bloco = texto[ini:texto.index("\n};", ini)]
    # get:(e,p)=>p.derivados.X  |  get:(e)=>e.mercado.X  |  get:(e,p)=>p.X
    achados = {}
    for linha in bloco.splitlines():
        m = re.match(r"\s{2}(\w+):\s*\{", linha)
        if not m:
            continue
        g = re.search(r"get:\([^)]*\)=>([\w.]+)", linha)
        achados[m.group(1)] = g.group(1) if g else None
    return achados


def test_todo_indicador_do_template_resolve_no_payload(metricas, payload):
    """Guard: cada getter de METRICAS tem que achar o campo no payload real."""
    assert metricas, "nao consegui ler METRICAS do template"
    empresa = payload["empresas"][0]
    faltando = []
    for nome, caminho in metricas.items():
        assert caminho, f"{nome}: sem getter reconhecivel"
        partes = caminho.split(".")
        # 'e' = empresa; 'p' = o periodo selecionado (usamos q_recente).
        no = empresa if partes[0] == "e" else empresa["q_recente"]
        for campo in partes[1:]:
            if not isinstance(no, dict) or campo not in no:
                faltando.append(f"{nome} -> {caminho}")
                break
            no = no[campo]
    assert not faltando, "METRICAS aponta para campo inexistente: " + "; ".join(faltando)


def test_contagem_de_indicadores_do_readme_bate_com_o_template():
    """Guard: o numero de indicadores era afirmado em tres lugares.

    README, CLAUDE.md e o badge do dashboard. O badge computa de METRICAS e
    nunca erra; os dois documentos eram escritos a mao e ja ficaram em 28
    depois que um indicador saiu. Em vez de fixar 27 aqui -- um quarto lugar
    para divergir --, este teste le o numero do README e confere contra o
    template, que e a fonte real.
    """
    tpl = (ROOT / "dashboard_template.html").read_text(encoding="utf-8")
    linhas = [ln for ln in tpl.splitlines() if re.match(r"\s{2}\w+:\s*\{", ln)
              and "label:" in ln]
    total = len(linhas)
    derivados = sum(1 for ln in linhas if "derivado:true" in ln)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*(\d+) indicadores\*\*.*?(\d+) primários e (\d+) derivados",
                  readme, re.S)
    assert m, "nao achei a contagem no README"
    r_total, r_prim, r_der = (int(x) for x in m.groups())

    assert r_total == total, f"README diz {r_total} indicadores, METRICAS tem {total}"
    assert r_der == derivados, f"README diz {r_der} derivados, METRICAS tem {derivados}"
    assert r_prim + r_der == r_total, f"README: {r_prim} + {r_der} != {r_total}"


def test_seletor_do_historico_so_oferece_derivado_que_o_build_publica(payload):
    """HIST_METRICAS filtra por METRICAS; o build publica a lista disponivel."""
    publicados = set(payload["meta_build"]["derivados_historico"])
    for e in payload["empresas"]:
        for h in e.get("historico") or []:
            assert set(h.get("derivados") or {}) <= publicados
