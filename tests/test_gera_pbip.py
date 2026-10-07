"""powerbi/gera_pbip.py: o universo "Escala" acrescenta CVX, BP e TTE à PoC (não troca as empresas)."""
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("gera_pbip", ROOT / "powerbi" / "gera_pbip.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def test_escala_contem_as_sete_empresas_e_a_poc_as_quatro():
    u = g.universos()
    poc = {e for nome, e, _ in u if nome == g.UNI_POC}
    esc = {e for nome, e, _ in u if nome == g.UNI_ESC}
    assert poc == {"PBR", "XOM", "SHEL", "EQNR"}
    assert esc == poc | {"CVX", "BP", "TTE"}


def test_ponte_filtra_dim_empresa_nos_dois_sentidos():
    mdl = g.modelo(True)["model"]
    rel = [r for r in mdl["relationships"] if r["fromTable"] == "dim_universo"]
    assert len(rel) == 1 and rel[0]["toTable"] == "dim_empresa" and rel[0]["crossFilteringBehavior"] == "bothDirections"
    medidas = {m["name"] for t in mdl["tables"] for m in t.get("measures", [])}
    assert {"Descrição do Universo", "Posição Petrobras (de N)", "Empresas no Universo"} <= medidas


def test_slicers_de_universo_sao_de_selecao_unica_na_ponte(tmp_path):
    ps = g.escreve(tmp_path / "p", True)
    slicers = [v for p in ps for v in p.visuais if v["visual"]["visualType"] == "slicer"
               and "universo" in json.dumps(v["visual"]["query"])]
    assert len(slicers) == 4
    for v in slicers:
        txt = json.dumps(v["visual"])
        assert '"Entity": "dim_universo"' in txt and "strictSingleSelect" in txt
    # nenhuma referência à antiga coluna dim_empresa[universo]
    assert '"Entity": "dim_empresa"}}, "Property": "universo"' not in json.dumps([v for p in ps for v in p.visuais])


def test_linhas_tem_cor_fixa_para_as_sete_empresas():
    ps = g.paginas()
    linhas = [v for p in ps for v in p.visuais if v["visual"]["visualType"] == "lineChart"]
    assert len(linhas) == 2
    for v in linhas:
        cods = {s["selector"]["data"][0]["scopeId"]["Comparison"]["Right"]["Literal"]["Value"].strip("'")
                for s in v["visual"]["objects"]["dataPoint"]}
        assert cods == {"PBR", "XOM", "SHEL", "EQNR", "CVX", "BP", "TTE"}


def test_tooltip_das_barras_usa_o_selo_do_proprio_indicador():
    ps = g.paginas()
    visao = next(p for p in ps if p.nome == "visao")
    barras = [v for v in visao.visuais if v["visual"]["visualType"] == "clusteredBarChart"]
    assert len(barras) == 3
    for v in barras:
        tt = v["visual"]["query"]["queryState"]["Tooltips"]["projections"][0]["field"]["Measure"]["Property"]
        assert tt.startswith("Selo · ")
