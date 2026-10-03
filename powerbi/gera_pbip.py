#!/usr/bin/env python3
"""Gera o projeto Power BI (PBIP: relatório PBIR + modelo semântico model.bim) da PoC.

    python3 powerbi/gera_pbip.py                 # fonte = CSVs do GitHub (parâmetro UrlBase)
    python3 powerbi/gera_pbip.py --embutido      # dados embutidos no modelo (abre offline)
    python3 powerbi/gera_pbip.py --saida DIR

Abrir: Power BI Desktop → Arquivo → Abrir → Benchmarking_Petrobras_Pares.pbip → Atualizar → Salvar.
O cache de dados (.pbi/cache.abf) só é gravado pelo Desktop ao salvar: sem ele, os visuais abrem em branco.
Para distribuir, use também Arquivo → Salvar como → .pbix (abre com os dados carregados).
O relatório replica o painel HTML (visão executiva, comparação, evolução, matriz,
qualidade e fontes) sobre o mesmo modelo estrela de poc/ (fato_indicador + dimensões).
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import shutil
import uuid
import zlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
POC = RAIZ / "poc"
NOME = "Benchmarking_Petrobras_Pares"
URL_BASE = "https://raw.githubusercontent.com/jmagomez/oil-gas-financial-dashboard/main/poc/"
SCH = "https://developer.microsoft.com/json-schemas/fabric"
NS = uuid.UUID("6f1c2a52-6a8e-4d0e-9a51-7b7f0c3a9e10")
CORES = ["#0F8F63", "#2A78D6", "#B07800", "#4A3AA7", "#EB6834", "#C2457A", "#6B7C8C"]


def gid(*partes):
    return str(uuid.uuid5(NS, "|".join(partes)))


def nid(*partes):
    return gid(*partes).replace("-", "")[:20]


# --------------------------------------------------------------------------- #
# Modelo semântico (TMSL / model.bim)
# --------------------------------------------------------------------------- #
TABELAS = {
    # tabela: (arquivo csv, [(coluna, tipo TMSL, tipo M, oculta, formato)])
    "fato_indicador": ("fato_indicador.csv", [
        ("empresa", "string", "type text", False, None), ("periodo", "string", "type text", True, None),
        ("rotulo", "string", "type text", True, None), ("indicador", "string", "type text", True, None),
        ("valor", "double", "type number", False, "#,0.00"), ("unidade", "string", "type text", False, None),
        ("status", "string", "type text", False, None), ("obs", "string", "type text", False, None),
        ("fonte", "string", "type text", False, None), ("hash", "string", "type text", True, None)]),
    "dim_empresa": ("dim_empresa.csv", [
        ("empresa", "string", "type text", False, None), ("nome", "string", "type text", False, None),
        ("pais", "string", "type text", False, None), ("padrao_contabil", "string", "type text", False, None),
        ("perfil", "string", "type text", False, None), ("na_poc", "boolean", "type logical", True, None),
        ("ordem", "int64", "Int64.Type", True, "0")]),
    "dim_periodo": ("dim_periodo.csv", [
        ("periodo", "string", "type text", False, None), ("rotulo", "string", "type text", False, None),
        ("ordem", "int64", "Int64.Type", True, "0"), ("data_fim", "dateTime", "type date", False, "dd/mm/yyyy"),
        ("dias", "int64", "Int64.Type", False, "0"), ("brent_medio", "double", "type number", False, "#,0.00")]),
    "dim_indicador": ("dim_indicador.csv", [
        ("indicador", "string", "type text", True, None), ("nome", "string", "type text", False, None),
        ("unidade", "string", "type text", False, None), ("direcao", "int64", "Int64.Type", False, "0"),
        ("casas", "int64", "Int64.Type", True, "0"), ("formula", "string", "type text", False, None),
        ("grupo", "string", "type text", False, None), ("ordem", "int64", "Int64.Type", True, "0")]),
    "dim_fonte": ("dim_fonte.csv", [
        ("id", "string", "type text", False, None), ("empresa", "string", "type text", False, None),
        ("tipo", "string", "type text", False, None), ("fonte", "string", "type text", False, None),
        ("url_primaria", "string", "type text", False, None), ("alternativa_direta", "string", "type text", False, None),
        ("coletado_em", "string", "type text", False, None), ("frequencia", "string", "type text", False, None),
        ("primaria", "boolean", "type logical", False, None)]),
    "qa_log": ("qa_log.csv", [
        ("empresa", "string", "type text", False, None), ("periodo", "string", "type text", False, None),
        ("campo", "string", "type text", False, None), ("regra", "string", "type text", False, None),
        ("severidade", "string", "type text", False, None), ("justificado", "boolean", "type logical", False, None),
        ("mensagem", "string", "type text", False, None), ("leitura", "string", "type text", False, None),
        ("fonte_leitura", "string", "type text", False, None)]),
}
ORDENA_POR = {("dim_empresa", "empresa"): "ordem", ("dim_empresa", "nome"): "ordem",
              ("dim_periodo", "rotulo"): "ordem", ("dim_periodo", "periodo"): "ordem",
              ("dim_indicador", "nome"): "ordem"}

IND_MEDIDAS = [  # medida por indicador: (nome, codigo, formato)
    ("Margem EBITDA (%)", "margem_ebitda", "#,0.0"), ("Margem líquida (%)", "margem_liquida", "#,0.0"),
    ("FCF (US$ bi)", "fcf", "#,0.0"), ("DL/EBITDA (x)", "nd_ebitda", "#,0.00"),
    ("EBITDA por boe (US$)", "ebitda_boe", "#,0.0"), ("Efetivo", "efetivo", "#,0"),
    ("EBITDA TTM por empregado (US$ mil)", "ebitda_por_empregado", "#,0"),
    ("DL sem arrendamentos/EBITDA (x)", "nd_ex_arrend_ebitda", "#,0.00"),
    ("Margem EBITDA ajustada (%)", "margem_ebitda_ajustada", "#,0.0"),
]


def medidas():
    m = [
        ("Valor Médio", "AVERAGE ( fato_indicador[valor] )", "#,0.##", "Base"),
        ("Valor Validado", 'CALCULATE ( AVERAGE ( fato_indicador[valor] ), KEEPFILTERS ( fato_indicador[status] <> "vermelho" ) )', "#,0.##", "Base"),
        ("Selo QA",
         'VAR r = CALCULATE ( COUNTROWS ( fato_indicador ), fato_indicador[status] = "vermelho" )\n'
         'VAR a = CALCULATE ( COUNTROWS ( fato_indicador ), fato_indicador[status] = "amarelo" )\n'
         'RETURN IF ( COUNTROWS ( fato_indicador ) = 0, BLANK (), IF ( r > 0, "✕ em análise", IF ( a > 0, "▲ ressalva", "✓ validado" ) ) )',
         None, "Base"),
        ("Valor Petrobras", 'CALCULATE ( [Valor Validado], dim_empresa[empresa] = "PBR" )', "#,0.##", "Petrobras"),
        # MEDIANX conta valor em branco como zero: empresa fora do universo filtrado (ou com valor em análise)
        # tem de ser excluída explicitamente, senão a mediana cai (achado no teste de 02/10/2026).
        ("Mediana Pares",
         'VAR pares = FILTER ( ALLSELECTED ( dim_empresa[empresa] ), dim_empresa[empresa] <> "PBR" && NOT ISBLANK ( [Valor Validado] ) )\n'
         'RETURN MEDIANX ( pares, [Valor Validado] )', "#,0.##", "Base"),
        ("Δ Petrobras vs. Mediana", "[Valor Petrobras] - [Mediana Pares]", "+#,0.00;-#,0.00;0", "Petrobras"),
        ("Δ t/t Petrobras",
         "VAR o = SELECTEDVALUE ( dim_periodo[ordem] )\n"
         "VAR atual = [Valor Petrobras]\n"
         "VAR ant = CALCULATE ( [Valor Petrobras], REMOVEFILTERS ( dim_periodo ), dim_periodo[ordem] = o - 1 )\n"
         "RETURN IF ( NOT ISBLANK ( atual ) && NOT ISBLANK ( ant ), atual - ant )", "+#,0.00;-#,0.00;0", "Petrobras"),
        ("Posição Petrobras",
         "VAR d = SELECTEDVALUE ( dim_indicador[direcao] )\n"
         "VAR v = [Valor Petrobras]\n"
         "VAR grupo = FILTER ( ALLSELECTED ( dim_empresa[empresa] ), NOT ISBLANK ( [Valor Validado] ) )\n"
         "RETURN IF ( d <> 0 && NOT ISBLANK ( v ), RANKX ( grupo, [Valor Validado] * d, v * d, DESC, DENSE ) )", "0", "Petrobras"),
        ("Brent Médio (US$/bbl)", "AVERAGE ( dim_periodo[brent_medio] )", "#,0.0", "Contexto"),
        ("% Validado",
         'DIVIDE ( CALCULATE ( COUNTROWS ( fato_indicador ), fato_indicador[status] = "verde" ), COUNTROWS ( fato_indicador ) )', "0%", "Qualidade"),
        ("Valores com ressalva", 'CALCULATE ( COUNTROWS ( fato_indicador ), fato_indicador[status] = "amarelo" ) + 0', "#,0", "Qualidade"),
        ("Valores em análise", 'CALCULATE ( COUNTROWS ( fato_indicador ), fato_indicador[status] = "vermelho" ) + 0', "#,0", "Qualidade"),
        ("Alertas", "COUNTROWS ( qa_log ) + 0", "#,0", "Qualidade"),
        ("Alertas pendentes", "CALCULATE ( COUNTROWS ( qa_log ), qa_log[justificado] = FALSE () ) + 0", "#,0", "Qualidade"),
        ("Alertas justificados", "CALCULATE ( COUNTROWS ( qa_log ), qa_log[justificado] = TRUE () ) + 0", "#,0", "Qualidade"),
    ]
    m.append(("Cor Destaque", 'IF ( SELECTEDVALUE ( dim_empresa[empresa] ) = "PBR", "#0F8F63", "#9AA9B6" )', None, "Formatação"))
    for nome, cod, fmt in IND_MEDIDAS:
        m.append((nome, f'CALCULATE ( [Valor Validado], dim_indicador[indicador] = "{cod}" )', fmt, "Indicadores"))
        m.append((f"PBR · {nome}", f'CALCULATE ( [Valor Petrobras], dim_indicador[indicador] = "{cod}" )', fmt, "Petrobras"))
        m.append((f"Mediana · {nome}", f'CALCULATE ( [Mediana Pares], dim_indicador[indicador] = "{cod}" )', fmt, "Mediana dos pares"))
    out = []
    for nome, expr, fmt, pasta in m:
        d = {"name": nome, "expression": expr.split("\n") if "\n" in expr else expr, "displayFolder": pasta,
             "lineageTag": gid("medida", nome)}
        if fmt:
            d["formatString"] = fmt
        out.append(d)
    return out


def m_embutido(tabela, arquivo, cols):
    linhas = list(csv.DictReader(open(POC / arquivo, encoding="utf-8")))
    bruto = json.dumps(linhas, ensure_ascii=False).encode("utf-8")
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    b64 = base64.b64encode(comp.compress(bruto) + comp.flush()).decode()
    tipos = ", ".join(f'{{"{c}", {m}}}' for c, _, m, _, _ in cols)
    return ["let",
            f'    Bin = Binary.Decompress ( Binary.FromText ( "{b64}", BinaryEncoding.Base64 ), Compression.Deflate ),',
            "    Linhas = Json.Document ( Bin, 65001 ),",
            "    Tabela = Table.FromRecords ( Linhas ),",
            '    Vazios = Table.ReplaceValue ( Tabela, "", null, Replacer.ReplaceValue, Table.ColumnNames ( Tabela ) ),',
            f'    Tipado = Table.TransformColumnTypes ( Vazios, {{{tipos}}}, "en-US" )',
            "in",
            "    Tipado"]


def m_web(tabela, arquivo, cols):
    tipos = ", ".join(f'{{"{c}", {m}}}' for c, _, m, _, _ in cols)
    return ["let",
            f'    Fonte = Csv.Document ( Web.Contents ( UrlBase & "{arquivo}" ), [ Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv ] ),',
            "    Cabecalho = Table.PromoteHeaders ( Fonte, [ PromoteAllScalars = true ] ),",
            '    Vazios = Table.ReplaceValue ( Cabecalho, "", null, Replacer.ReplaceValue, Table.ColumnNames ( Cabecalho ) ),',
            f'    Tipado = Table.TransformColumnTypes ( Vazios, {{{tipos}}}, "en-US" )',
            "in",
            "    Tipado"]


def modelo(embutido):
    tabelas = []
    for t, (arq, cols) in TABELAS.items():
        colunas = []
        for c, tipo, _, oculta, fmt in cols:
            d = {"name": c, "dataType": tipo, "sourceColumn": c, "lineageTag": gid("col", t, c),
                 "summarizeBy": "none", "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}]}
            if oculta:
                d["isHidden"] = True
            if fmt:
                d["formatString"] = fmt
            if (t, c) in ORDENA_POR:
                d["sortByColumn"] = ORDENA_POR[(t, c)]
            colunas.append(d)
        expr = m_embutido(t, arq, cols) if embutido else m_web(t, arq, cols)
        tab = {"name": t, "lineageTag": gid("tab", t), "columns": colunas,
               "partitions": [{"name": t, "mode": "import", "source": {"type": "m", "expression": expr}}],
               "annotations": [{"name": "PBI_ResultType", "value": "Table"}]}
        if t == "fato_indicador":
            tab["measures"] = medidas()
        tabelas.append(tab)
    # Power BI recusa (sem mensagem de erro) modelos em que uma medida tem o mesmo nome
    # de uma coluna (comparação sem diferenciar maiúsculas) — falha observada no teste em 02/10/2026.
    nomes_col = {c["name"].lower() for tb in tabelas for c in tb["columns"]}
    colisao = [md["name"] for tb in tabelas for md in tb.get("measures", []) if md["name"].lower() in nomes_col]
    if colisao:
        raise SystemExit(f"Medidas com nome igual a coluna: {colisao}")
    rel = [("fato_indicador", "empresa", "dim_empresa", "empresa"), ("fato_indicador", "periodo", "dim_periodo", "periodo"),
           ("fato_indicador", "indicador", "dim_indicador", "indicador"), ("fato_indicador", "fonte", "dim_fonte", "id"),
           ("qa_log", "empresa", "dim_empresa", "empresa")]
    model = {
        "culture": "pt-BR",
        "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
        "defaultPowerBIDataSourceVersion": "powerBI_V3",
        "sourceQueryCulture": "pt-BR",
        "tables": tabelas,
        "relationships": [{"name": gid("rel", *r), "fromTable": r[0], "fromColumn": r[1], "toTable": r[2], "toColumn": r[3]} for r in rel],
        "annotations": [{"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
                        {"name": "PBI_QueryOrder", "value": json.dumps((["UrlBase"] if not embutido else []) + list(TABELAS))}],
    }
    if not embutido:
        model["expressions"] = [{
            "name": "UrlBase", "kind": "m", "lineageTag": gid("expr", "UrlBase"),
            "expression": f'"{URL_BASE}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]',
            "annotations": [{"name": "PBI_ResultType", "value": "Text"}]}]
    return {"compatibilityLevel": 1567, "model": model}


# --------------------------------------------------------------------------- #
# Relatório (PBIR)
# --------------------------------------------------------------------------- #
def lit(v):
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}}


def col(t, c):
    return {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}}


def med(c):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "fato_indicador"}}, "Property": c}}


def proj(campo, nome=None):
    k = "Column" if "Column" in campo else "Measure"
    ent = campo[k]["Expression"]["SourceRef"]["Entity"]
    prop = campo[k]["Property"]
    d = {"field": campo, "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}
    if nome:
        d["displayName"] = nome
    return d


LOGO = "petrobras_logo.png"
LOGO_B64 = RAIZ / "poc" / "assets" / "petrobras_logo.b64"


class Pagina:
    def __init__(self, nome, titulo):
        self.nome, self.titulo, self.visuais, self.interacoes = nome, titulo, [], []

    def add(self, nome, tipo, x, y, w, h, papeis=None, titulo=None, objetos=None, ordem=None):
        v = {"visualType": tipo, "drillFilterOtherVisuals": True}
        if papeis:
            v["query"] = {"queryState": {r: {"projections": [proj(*c) if isinstance(c, tuple) else proj(c) for c in cs]} for r, cs in papeis.items()}}
            if ordem:
                v["query"]["sortDefinition"] = {"sort": [{"field": ordem[0], "direction": ordem[1]}], "isDefaultSort": False}
        if objetos:
            v["objects"] = objetos
        vco = {}
        if titulo:
            vco["title"] = [{"properties": {"show": lit(True), "text": lit(titulo)}}]
        if vco:
            v["visualContainerObjects"] = vco
        vid = nid(self.nome, nome)
        self.visuais.append({"$schema": f"{SCH}/item/report/definition/visualContainer/2.0.0/schema.json",
                             "name": vid, "position": {"x": x, "y": y, "z": len(self.visuais) * 1000, "width": w, "height": h,
                                                       "tabOrder": len(self.visuais) * 1000}, "visual": v})
        return vid

    def logo(self, x, y, w, h):
        img = {"imageUrl": {"expr": {"ResourcePackageItem": {"PackageName": "RegisteredResources", "PackageType": 1,
                                                                "ItemName": LOGO}}}}
        return self.add("logo", "image", x, y, w, h, objetos={"general": [{"properties": img}]})

    def texto(self, nome, texto, x, y, w, h, tamanho=20, negrito=True, cor="#13202B"):
        if nome == "t" and LOGO_B64.exists():  # título de página: logo da Petrobras à esquerda
            self.logo(x, y + 9, 128, 25)
            x, w = x + 140, w - 140
            if len(texto) > 34:  # título longo: reduz a fonte para caber ao lado do logo
                tamanho = min(tamanho, 16)
        par = [{"textRuns": [{"value": texto, "textStyle": {"fontWeight": "bold" if negrito else "normal",
                                                           "fontSize": f"{tamanho}pt", "color": cor}}]}]
        return self.add(nome, "textbox", x, y, w, h, objetos={"general": [{"properties": {"paragraphs": par}}]})

    def slicer(self, nome, campo, x, y, w, h, titulo, dropdown=True, unico=False, padrao=None):
        # cabeçalho do slicer oculto: o título do contêiner já nomeia o campo e o cabeçalho cortava a lista suspensa
        obj = {"data": [{"properties": {"mode": lit("Dropdown" if dropdown else "Basic")}}],
               "header": [{"properties": {"show": lit(False)}}]}
        if unico:
            obj["selection"] = [{"properties": {"strictSingleSelect": lit(True)}}]
        if padrao is not None:
            # seleção inicial explícita: sem ela o Power BI escolhe o 1º item (1T25) em slicers de seleção única
            ent, prop = campo["Column"]["Expression"]["SourceRef"]["Entity"], campo["Column"]["Property"]
            flt = {"Version": 2, "From": [{"Name": "s", "Entity": ent, "Type": 0}],
                   "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": prop}}],
                                                   "Values": [[lit(padrao)["expr"]]]}}}]}
            obj["general"] = [{"properties": {"filter": {"filter": flt}}}]
        return self.add(nome, "slicer", x, y, w, h, {"Values": [campo]}, titulo, obj)

    def sem_filtro(self, origem, *alvos):
        for a in alvos:
            self.interacoes.append({"source": origem, "target": a, "type": "NoFilter"})


def cor_fixa(hexa):
    return {"dataPoint": [{"properties": {"fill": {"solid": {"color": lit(hexa)}}}}]}


def cor_por_medida(medida):
    # formatação condicional por valor de campo: Petrobras em verde, pares em cinza
    return {"dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": med(medida)}}}},
                           "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]}


def junta(*objs):
    out = {}
    for o in objs:
        for k, v in o.items():
            out.setdefault(k, []).extend(v)
    return out


SEM_TOTAIS = {"subTotals": [{"properties": {"rowSubtotals": lit(False), "columnSubtotals": lit(False)}}]}
TABELA_SEM_TOTAL = {"total": [{"properties": {"totals": lit(False)}}]}
CARTAO_NUM_INTEIRO = {"labels": [{"properties": {"labelDisplayUnits": lit(1)}}]}
ROTULOS = {"labels": [{"properties": {"show": lit(True)}}]}
GRADE = {k: [{"properties": {"fontSize": lit(11)}}] for k in ("values", "columnHeaders", "rowHeaders")}
GRADE_TAB = {k: [{"properties": {"fontSize": lit(10)}}] for k in ("values", "columnHeaders")}
CARTAO_DUPLO = {"dataLabels": [{"properties": {"fontSize": lit(14)}}], "categoryLabels": [{"properties": {"fontSize": lit(8)}}],
                "card": [{"properties": {"barShow": lit(False)}}]}


def ultimo_periodo():
    linhas = list(csv.DictReader(open(POC / "dim_periodo.csv", encoding="utf-8")))
    return max(linhas, key=lambda r: int(r["ordem"]))["rotulo"]


UNI_POC = "PoC (PBR + 3 pares)"  # mesmo recorte padrão do painel HTML


def paginas():
    ULT = ultimo_periodo()
    E, P, IN = col("dim_empresa", "empresa"), col("dim_periodo", "rotulo"), col("dim_indicador", "nome")
    U = col("dim_empresa", "universo")
    ps = []

    # 1 — Visão executiva
    p = Pagina("visao", "Visão executiva")
    p.texto("t", "Petrobras vs. pares — visão executiva do trimestre", 20, 12, 820, 44)
    p.texto("st", "Fontes públicas · indicadores recalculados com a mesma fórmula · valores em análise (✕) ficam fora de medianas e rankings",
            20, 52, 900, 26, tamanho=10, negrito=False, cor="#46566A")
    sp = p.slicer("sp", P, 1060, 12, 200, 60, "Período", unico=True, padrao=ULT)
    p.slicer("su", U, 850, 12, 200, 60, "Universo", padrao=UNI_POC)
    cards = []
    for k, (nome, _, _) in enumerate(IND_MEDIDAS[:6]):
        cards.append(p.add(f"c{k}", "multiRowCard", 20 + k * 208, 82, 200, 136,
                           {"Values": [(med(f"PBR · {nome}"), "Petrobras"), (med(f"Mediana · {nome}"), "Mediana dos pares")]}, nome, CARTAO_DUPLO))
    for cod, (nome, _, _), x, w in [("b1", IND_MEDIDAS[0], 20, 410), ("b2", IND_MEDIDAS[3], 440, 410), ("b3", IND_MEDIDAS[2], 860, 400)]:
        p.add(cod, "clusteredBarChart", x, 224, w, 226, {"Category": [(E, "Empresa")], "Y": [med(nome)]},
              {"b1": "Margem EBITDA (%) por empresa", "b2": "Dívida líquida / EBITDA TTM (x)", "b3": "Fluxo de caixa livre (US$ bi)"}[cod],
              junta(cor_por_medida("Cor Destaque"), ROTULOS), ordem=(med(nome), "Descending"))
    l1 = p.add("l1", "lineChart", 20, 458, 830, 252, {"Category": [(P, "Trimestre")], "Series": [(E, "Empresa")], "Y": [med("Margem EBITDA (%)")]},
               "Evolução da margem EBITDA (%) — série completa")
    l2 = p.add("l2", "clusteredColumnChart", 860, 458, 400, 252, {"Category": [(P, "Trimestre")], "Y": [med("Brent Médio (US$/bbl)")]},
               "Contexto: Brent médio (US$/bbl)", junta(cor_fixa("#6B7C8C"), ROTULOS))
    p.sem_filtro(sp, l1, l2)
    ps.append(p)

    # 2 — Comparação e evolução
    p = Pagina("comparacao", "Comparação e evolução")
    p.texto("t", "Comparação e evolução histórica", 20, 12, 700, 44)
    p.slicer("si", IN, 640, 12, 260, 60, "Indicador", unico=True, padrao="Margem EBITDA")
    sp = p.slicer("sp", P, 910, 12, 160, 60, "Período", unico=True, padrao=ULT)
    p.slicer("su", U, 1080, 12, 180, 60, "Universo", padrao=UNI_POC)
    p.add("b", "clusteredBarChart", 20, 86, 620, 300, {"Category": [(E, "Empresa")], "Y": [(med("Valor Validado"), "Valor")]},
              "Valor por empresa no período", junta(cor_por_medida("Cor Destaque"), ROTULOS), ordem=(med("Valor Validado"), "Descending"))
    ln = p.add("l", "lineChart", 650, 86, 610, 300, {"Category": [(P, "Trimestre")], "Series": [(E, "Empresa")], "Y": [(med("Valor Validado"), "Valor")]},
              "Evolução trimestral")
    m = p.add("m", "pivotTable", 20, 396, 1240, 310, {"Rows": [(col("dim_empresa", "nome"), "Empresa")], "Columns": [(P, "Trimestre")],
                                                       "Values": [(med("Valor Validado"), "Valor")]},
              "Série trimestral (valor validado)", junta(SEM_TOTAIS, GRADE))
    p.sem_filtro(sp, ln, m)
    ps.append(p)

    # 3 — Matriz de leitura
    p = Pagina("matriz", "Matriz de leitura")
    p.texto("t", "Leitura dos indicadores — matriz do trimestre", 20, 12, 800, 44)
    p.slicer("sp", P, 900, 12, 170, 60, "Período", unico=True, padrao=ULT)
    p.slicer("su", U, 1080, 12, 180, 60, "Universo", padrao=UNI_POC)
    p.add("m", "pivotTable", 20, 86, 1240, 330, {"Rows": [(IN, "Indicador")], "Columns": [(E, "Empresa")], "Values": [(med("Valor Validado"), "Valor")]},
          "Indicador × empresa (valores validados)", junta(SEM_TOTAIS, GRADE))
    p.add("d", "tableEx", 20, 426, 820, 280, {"Values": [(IN, "Indicador"), (col("dim_indicador", "unidade"), "Unidade"),
                                                         (col("dim_indicador", "formula"), "Fórmula")]}, "Definições", GRADE_TAB)
    p.add("pp", "tableEx", 850, 426, 410, 280, {"Values": [(IN, "Indicador"), (med("Valor Petrobras"), "Petrobras"), (med("Mediana Pares"), "Mediana pares"),
                                                            (med("Posição Petrobras"), "Posição")]}, "Petrobras vs. mediana dos pares", junta(TABELA_SEM_TOTAL, GRADE_TAB))
    ps.append(p)

    # 4 — Qualidade
    p = Pagina("qualidade", "Qualidade e rastreabilidade")
    p.texto("t", "Qualidade e rastreabilidade dos dados", 20, 12, 800, 44)
    p.slicer("su", U, 850, 12, 200, 60, "Universo", padrao=UNI_POC)
    p.slicer("se", E, 1060, 12, 200, 60, "Empresa")
    for k, (n, t) in enumerate([("% Validado", "Valores validados sem ressalva"), ("Valores com ressalva", "Valores com ressalva (▲)"),
                                ("Valores em análise", "Valores em análise (✕)"), ("Alertas pendentes", "Alertas pendentes de leitura")]):
        p.add(f"c{k}", "card", 20 + k * 312, 86, 300, 100, {"Values": [med(n)]}, t)
    p.add("r", "clusteredBarChart", 20, 196, 500, 510, {"Category": [(col("qa_log", "regra"), "Regra")],
                                                         "Y": [(med("Alertas pendentes"), "Pendentes"), (med("Alertas justificados"), "Justificados")]},
          "Alertas por regra", junta({"dataPoint": [{"properties": {"fill": {"solid": {"color": lit("#A86A00")}}},
                                                     "selector": {"metadata": "fato_indicador.Alertas pendentes"}},
                                                    {"properties": {"fill": {"solid": {"color": lit("#D9C6A0")}}},
                                                     "selector": {"metadata": "fato_indicador.Alertas justificados"}}]}, ROTULOS))
    p.add("q", "tableEx", 530, 196, 730, 510, {"Values": [(col("qa_log", "empresa"), "Empresa"), (col("qa_log", "trimestre"), "Período"),
                                                           (col("qa_log", "campo"), "Campo"), (col("qa_log", "regra"), "Regra"),
                                                           (col("qa_log", "situacao"), "Situação"), (col("qa_log", "mensagem"), "Mensagem"),
                                                           (col("qa_log", "leitura"), "Leitura do release")]},
          "Log de alertas", GRADE_TAB, ordem=(col("qa_log", "situacao"), "Descending"))
    ps.append(p)

    # 5 — Fontes
    p = Pagina("fontes", "Fontes e metodologia")
    p.texto("t", "Catálogo de fontes", 20, 12, 800, 44)
    p.add("f", "tableEx", 20, 70, 1240, 500, {"Values": [(col("dim_fonte", c), n) for c, n in [
        ("id", "ID"), ("empresa", "Empresa"), ("tipo", "Dado"), ("fonte", "Fonte utilizada"), ("classe", "Tipo de fonte"),
        ("coletado_em", "Coleta"), ("alternativa_direta", "Rota primária / observação"), ("url_primaria", "Link")]]},
          "Fontes utilizadas e rota primária", GRADE_TAB)
    p.texto("m", "Selo de qualidade: ✓ validado · ▲ ressalva (dado carregado, proxy ou desvio a ler) · ✕ em análise (fora de medianas e rankings). "
                 "Regras R1–R8: completude, coerência contábil, plausibilidade, desvio histórico, contexto (Brent), revisão, proveniência e "
                 "reconciliação entre fontes. Série 1T25–2T26 de releases oficiais (poc/coleta/); Petrobras pela PTAX do Banco Central "
                 "(média para fluxos, fechamento para dívida). Alertas explicados pelo release têm a leitura e o link em qa_log. "
                 "Detalhes no guia e em poc/build_poc.py.", 20, 584, 1240, 100, tamanho=11, negrito=False, cor="#46566A")
    ps.append(p)
    return ps


def tema():
    return {"name": "Benchmarking OG", "dataColors": CORES + ["#13202B", "#46566A", "#0B4F6C"],
            "foreground": "#13202B", "background": "#FFFFFF", "tableAccent": "#0B4F6C",
            "good": "#0F7A3D", "neutral": "#A86A00", "bad": "#C0392B", "maximum": "#0B4F6C", "minimum": "#E6EEF3", "center": "#9DB7C6",
            "textClasses": {"title": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": "#13202B"},
                            "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": "#46566A"},
                            "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 24, "color": "#13202B"}}}


def deriva(mdl, tabela, coluna, expr_m):
    """Acrescenta uma coluna calculada no Power Query da tabela (mesmo critério do painel HTML)."""
    tb = next(t for t in mdl["model"]["tables"] if t["name"] == tabela)
    tb["columns"].append({"name": coluna, "dataType": "string", "sourceColumn": coluna,
                          "lineageTag": gid("col", tabela, coluna), "summarizeBy": "none"})
    exp = tb["partitions"][0]["source"]["expression"]
    ultimo = exp[-1].strip()
    i = next(k for k, linha in enumerate(exp) if linha.strip().startswith(ultimo + " ="))
    exp[i] = exp[i].rstrip(",") + ","
    passo = f"Col_{coluna}"
    exp.insert(i + 1, f'    {passo} = Table.AddColumn ( {ultimo}, "{coluna}", each {expr_m}, type text )')
    exp[-1] = f"    {passo}"


def escreve(dest: Path, embutido: bool):
    if dest.exists():
        shutil.rmtree(dest)
    rep, sm = dest / f"{NOME}.Report", dest / f"{NOME}.SemanticModel"
    def j(p, o):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(o, ensure_ascii=False, indent=2), encoding="utf-8")
    j(dest / f"{NOME}.pbip", {"$schema": f"{SCH}/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
                              "artifacts": [{"report": {"path": f"{NOME}.Report"}}], "settings": {"enableAutoRecovery": True}})
    j(sm / ".platform", {"$schema": f"{SCH}/gitIntegration/platformProperties/2.0.0/schema.json",
                         "metadata": {"type": "SemanticModel", "displayName": NOME}, "config": {"version": "2.0", "logicalId": gid("sm")}})
    j(sm / "definition.pbism", {"$schema": f"{SCH}/item/semanticModel/definitionProperties/1.0.0/schema.json", "version": "1.0", "settings": {}})
    mdl = modelo(embutido)
    # colunas derivadas em Power Query (texto amigável para slicers e tabelas)
    deriva(mdl, "dim_empresa", "universo", 'if [na_poc] then "PoC (PBR + 3 pares)" else "Escala (+3)"')
    deriva(mdl, "qa_log", "situacao", 'if [justificado] then (if [leitura] <> null and [leitura] <> "" then "explicado pelo release" else "justificado pelo contexto") else "pendente de leitura"')
    deriva(mdl, "qa_log", "trimestre",
           'if Text.Contains ( [periodo], "-Q" ) then Text.End ( [periodo], 1 ) & "T" & Text.Middle ( [periodo], 2, 2 ) else [periodo]')
    deriva(mdl, "dim_fonte", "classe",
           'if [primaria] then "primária" else if Text.Contains ( Text.Lower ( [tipo] ), "agregador" ) then "agregador" else "secundária"')
    j(sm / "model.bim", mdl)
    j(rep / ".platform", {"$schema": f"{SCH}/gitIntegration/platformProperties/2.0.0/schema.json",
                          "metadata": {"type": "Report", "displayName": NOME}, "config": {"version": "2.0", "logicalId": gid("rep")}})
    j(rep / "definition.pbir", {"$schema": f"{SCH}/item/report/definitionProperties/2.0.0/schema.json", "version": "4.0",
                                "datasetReference": {"byPath": {"path": f"../{NOME}.SemanticModel"}}})
    d = rep / "definition"
    j(d / "version.json", {"$schema": f"{SCH}/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    j(d / "report.json", {
        "$schema": f"{SCH}/item/report/definition/report/2.0.0/schema.json",
        "themeCollection": {"baseTheme": {"name": "CY24SU10", "reportVersionAtImport": "5.61", "type": "SharedResources"},
                            "customTheme": {"name": "BenchmarkingOG.json", "reportVersionAtImport": "5.61", "type": "RegisteredResources"}},
        "resourcePackages": [{"name": "SharedResources", "type": "SharedResources",
                              "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
                             {"name": "RegisteredResources", "type": "RegisteredResources",
                              "items": [{"name": "BenchmarkingOG.json", "path": "BenchmarkingOG.json", "type": "CustomTheme"}]
                              + ([{"name": LOGO, "path": LOGO, "type": "Image"}] if LOGO_B64.exists() else [])}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True}})
    base = tema()
    base["name"] = "CY24SU10"
    j(rep / "StaticResources" / "SharedResources" / "BaseThemes" / "CY24SU10.json", base)
    j(rep / "StaticResources" / "RegisteredResources" / "BenchmarkingOG.json", tema())
    if LOGO_B64.exists():
        import base64
        (rep / "StaticResources" / "RegisteredResources" / LOGO).write_bytes(base64.b64decode("".join(LOGO_B64.read_text().split())))
    ps = paginas()
    j(d / "pages" / "pages.json", {"$schema": f"{SCH}/item/report/definition/pagesMetadata/1.0.0/schema.json",
                                   "pageOrder": [nid("pg", p.nome) for p in ps], "activePageName": nid("pg", ps[0].nome)})
    for p in ps:
        pid = nid("pg", p.nome)
        pg = {"$schema": f"{SCH}/item/report/definition/page/2.0.0/schema.json", "name": pid, "displayName": p.titulo,
              "displayOption": "FitToPage", "height": 720, "width": 1280}
        if p.interacoes:
            pg["visualInteractions"] = p.interacoes
        j(d / "pages" / pid / "page.json", pg)
        for v in p.visuais:
            j(d / "pages" / pid / "visuals" / v["name"] / "visual.json", v)
    (dest / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n", encoding="utf-8")
    return ps


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--embutido", action="store_true", help="embute os dados no modelo (abre e atualiza offline)")
    ap.add_argument("--saida", default=str(RAIZ / "powerbi" / "projeto"))
    a = ap.parse_args(argv)
    ps = escreve(Path(a.saida), a.embutido)
    print(f"OK: PBIP em {a.saida} ({len(ps)} páginas, {sum(len(p.visuais) for p in ps)} visuais, "
          f"{'dados embutidos' if a.embutido else 'fonte = ' + URL_BASE})")


if __name__ == "__main__":
    main()
