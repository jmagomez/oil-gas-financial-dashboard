#!/usr/bin/env python3
"""Gera o corpo HTML do e-mail diario da rotina de dados de mercado.

Le o relatorio produzido por update_market_data.py (--relatorio) e o JSON
primario, e monta um retrato do fechamento. Reaproveita build_dashboard para a
camada derivada e para a validacao, de modo que e-mail, dashboard e CSV nunca
divirjam.

Principios do formato
---------------------
1. E um e-mail de ESTADO, nao de diff. A lista campo-a-campo do que mudou saiu:
   ela repetia em texto o que a tabela ja mostra, e crescia ate ~35 linhas de
   numeros que ninguem le. A variacao do dia continua, como coluna.
2. Numero sozinho nao informa. P/E 20,56 so significa algo contra o grupo, por
   isso a linha de mediana no rodape da tabela.
3. Alerta que se repete todo dia deixa de ser alerta. O que exige acao (valor
   recusado, ticker sem resposta) fica no topo, destacado; o que e caracteristica
   permanente da base vai para o rodape, com nome que nao promete incidente.

Uso:
    python3 build_email.py --relatorio caminho/relatorio-mercado.json
"""
import argparse
import datetime as dt
import html
import json
import statistics
from pathlib import Path

import build_dashboard as bd

BASE = Path(__file__).resolve().parent
OUT = BASE / "email_body.html"

# Colunas do quadro de mercado: (chave, rotulo, casas, onde_buscar)
# "mercado"  -> bloco de mercado da empresa
# "derivado" -> camada derivada do ano fiscal (calculada por build_dashboard)
CAMPOS = [
    ("preco_acao", "Preço<br><span style='font-weight:400;color:#888'>US$</span>", 2, "mercado"),
    ("market_cap", "Market cap<br><span style='font-weight:400;color:#888'>US$ mi</span>", 0, "mercado"),
    ("pe", "P/E", 2, "mercado"),
    ("ev_ebitda", "EV/EBITDA", 2, "mercado"),
    ("dividend_yield_pct", "Div. yield<br><span style='font-weight:400;color:#888'>%</span>", 2, "mercado"),
    ("fcf_yield_pct", "FCF yield<br><span style='font-weight:400;color:#888'>% · FY2025</span>", 2, "derivado"),
]

# Colunas em que a mediana do grupo ajuda a julgar o valor individual.
# Preco e market cap nao entram: mediana de escala nao diz nada.
COM_MEDIANA = {"pe", "ev_ebitda", "dividend_yield_pct", "fcf_yield_pct"}

BORDA = "border-bottom:1px solid #eee"


def num(v, casas=2):
    """Formata no padrao brasileiro: 1.234,56. Nunca aplicar sobre HTML."""
    if v is None:
        return "—"
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def valor_do_campo(empresa, chave, origem):
    if origem == "mercado":
        return empresa["mercado"].get(chave)
    return empresa["fy2025"]["derivados"].get(chave)


def var_por_ticker(relatorio):
    """{ticker: variacao % do preco da acao} a partir das mudancas do relatorio."""
    out = {}
    for m in relatorio.get("mudancas", []):
        if m.get("campo") == "preco_acao" and m.get("var_pct") is not None:
            out[m["ticker"]] = m["var_pct"]
    return out


def bloco_alertas(relatorio):
    """Rejeicoes e falhas sao o sinal de que a fonte mudou ou caiu.

    E o unico conteudo do e-mail que exige acao, entao vai no topo e destacado.
    """
    linhas = []
    for r in relatorio.get("rejeicoes", []):
        linhas.append(
            f"<b>{html.escape(r['ticker'])} · {html.escape(r['campo'])}</b>: valor "
            f"{html.escape(str(r['valor']))} recusado — {html.escape(r['motivo'])} "
            f"(mantido {html.escape(str(r['mantido']))})"
        )
    for f in relatorio.get("falhas", []):
        linhas.append(f"<b>{html.escape(f['ticker'])}</b>: {html.escape(f['motivo'])}")
    if not linhas:
        return ""
    return (
        "<div style='background:#fdecea;border:1px solid #f5c6cb;color:#8a1c1c;"
        "padding:10px 12px;border-radius:6px;margin:0 0 16px;font-size:13px;line-height:1.6'>"
        f"<b>Exige atenção: {len(linhas)} valor(es) não aceito(s) nesta execução.</b><br>"
        "O valor anterior foi mantido — nada suspeito é gravado por cima de um número bom.<br><br>"
        + "<br>".join(linhas)
        + "</div>"
    )


def bloco_tabela(data, variacoes):
    """Quadro principal: retrato do fechamento, com mediana do grupo no rodape."""
    # Ordena por market cap: a leitura comeca pelas maiores, nao pela ordem do arquivo.
    empresas = sorted(
        data["empresas"],
        key=lambda e: (e["mercado"].get("market_cap") or 0),
        reverse=True,
    )

    cab = "".join(
        f"<th scope='col' style='padding:7px 10px;text-align:right;{BORDA}'>{rot}</th>"
        for _, rot, _, _ in CAMPOS
    )

    linhas = []
    for i, e in enumerate(empresas):
        v = variacoes.get(e["ticker"])
        cor = "#666" if v is None else ("#0a7a2f" if v >= 0 else "#c0392b")
        vtxt = "—" if v is None else f"{v:+.2f}%".replace(".", ",")
        fundo = "background:#fafafa;" if i % 2 else ""
        celulas = "".join(
            f"<td style='padding:7px 10px;{BORDA};text-align:right;{fundo}'>"
            f"{num(valor_do_campo(e, c, origem), casas)}</td>"
            for c, _, casas, origem in CAMPOS
        )
        linhas.append(
            f"<tr><th scope='row' style='padding:7px 10px;{BORDA};text-align:left;"
            f"font-weight:400;{fundo}'>"
            f"<b>{html.escape(e['ticker'])}</b> "
            f"<span style='color:#999;font-size:12px'>{html.escape(e['nome'])}</span></th>"
            f"{celulas}"
            f"<td style='padding:7px 10px;{BORDA};text-align:right;color:{cor};{fundo}'>"
            f"{vtxt}</td></tr>"
        )

    # Mediana: da escala ao numero individual. Calculada dos dados presentes,
    # ignorando ausentes -- nunca preenche buraco com estimativa.
    medianas = []
    for c, _, casas, origem in CAMPOS:
        if c not in COM_MEDIANA:
            medianas.append(
                f"<td style='padding:7px 10px;text-align:right;color:#999'>—</td>"
            )
            continue
        vals = [valor_do_campo(e, c, origem) for e in empresas]
        vals = [x for x in vals if isinstance(x, (int, float))]
        medianas.append(
            f"<td style='padding:7px 10px;text-align:right;color:#555'>"
            f"{num(statistics.median(vals), casas) if vals else '—'}</td>"
        )

    return (
        "<table style='border-collapse:collapse;width:100%;font-size:13px' role='table'>"
        "<caption style='caption-side:top;text-align:left;font-size:12px;color:#888;"
        "padding-bottom:6px'>Fechamento das 7 majors, ordenado por market cap. "
        "Mediana do grupo no rodapé, para dar escala aos múltiplos.</caption>"
        "<thead><tr style='background:#f5f5f5'>"
        f"<th scope='col' style='padding:7px 10px;text-align:left;{BORDA}'>Empresa</th>"
        f"{cab}"
        f"<th scope='col' style='padding:7px 10px;text-align:right;{BORDA}'>"
        "Var. dia</th></tr></thead>"
        f"<tbody>{''.join(linhas)}</tbody>"
        "<tfoot><tr style='background:#f5f5f5;font-size:12px'>"
        "<th scope='row' style='padding:7px 10px;text-align:left;color:#555'>Mediana</th>"
        f"{''.join(medianas)}"
        "<td style='padding:7px 10px'></td></tr></tfoot>"
        "</table>"
    )


def bloco_observacoes(problemas):
    """Caracteristicas permanentes da base -- nao sao incidentes do dia.

    Antes isto se chamava "Avisos de validacao" e repetia as mesmas duas linhas
    todo dia. Alerta que nunca muda deixa de ser lido, e no dia em que aparecer
    um terceiro item de verdade ele some no meio dos dois de sempre. O nome
    agora diz o que a lista e; o que exige acao esta em bloco_alertas, no topo.
    """
    if not problemas:
        return ""
    itens = "".join(f"<li style='margin-bottom:3px'>{html.escape(p)}</li>" for p in problemas)
    return (
        "<div style='margin-top:18px;padding:10px 12px;background:#f7f7f7;"
        "border-left:3px solid #d0d0d0;border-radius:4px'>"
        f"<div style='font-size:13px;color:#555;font-weight:bold;margin-bottom:6px'>"
        f"Ressalvas conhecidas da base ({len(problemas)})</div>"
        "<div style='font-size:12px;color:#888;margin-bottom:6px'>"
        "Características estáveis dos dados, não ocorrências desta execução.</div>"
        f"<ul style='margin:0;padding-left:18px;font-size:12px;color:#666;line-height:1.5'>{itens}</ul>"
        "</div>"
    )


def montar(relatorio, data, pages_url=""):
    variacoes = var_por_ticker(relatorio)
    problemas = bd.validate(data)
    ref = data.get("referencia", {})
    # periodo_trimestral, e nao data_consulta: este ultimo e a data da coleta
    # original dos fundamentos e nao acompanha as atualizacoes, entao vinha
    # afirmando no e-mail uma referencia que ja nao era verdade.
    periodo = ref.get("periodo_trimestral", "—")
    atualizado = ref.get("atualizado_em", "—")
    gerado = relatorio.get("gerado_em", dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
    link = (
        f"<p style='margin-top:16px'><a href='{html.escape(pages_url)}' style='color:#1a56db'>"
        "Abrir dashboard completo</a></p>"
        if pages_url
        else ""
    )
    return f"""
<div style="font-family:Arial,Helvetica,sans-serif;max-width:760px">
  <h2 style="margin-bottom:4px">Óleo &amp; Gás — fechamento de mercado</h2>
  <p style="color:#666;margin-top:0;font-size:13px;line-height:1.6">
    Preço, market cap e múltiplos das 7 majors, após o fechamento de Nova York.
    O FCF yield vem dos fundamentos, que são curados a cada balanço e não mudam
    nesta rotina — trimestre de referência: <b>{html.escape(str(periodo))}</b>,
    base atualizada em {html.escape(str(atualizado))}.
  </p>
  {bloco_alertas(relatorio)}
  {bloco_tabela(data, variacoes)}
  {bloco_observacoes(problemas)}
  {link}
  <p style="color:#999;font-size:12px;margin-top:14px">
    Gerado automaticamente em {html.escape(str(gerado))} · mercado: Yahoo Finance ·
    fundamentos: releases das empresas. Uso informativo, não é recomendação de investimento.
  </p>
</div>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--relatorio", type=Path, required=True)
    ap.add_argument("--pages-url", default="")
    ap.add_argument("--saida", type=Path, default=OUT)
    args = ap.parse_args(argv)

    relatorio = json.loads(args.relatorio.read_text(encoding="utf-8")) if args.relatorio.exists() else {}
    data = bd.enriquecer(json.loads(bd.JSON_PATH.read_text(encoding="utf-8")))
    args.saida.write_text(montar(relatorio, data, args.pages_url), encoding="utf-8")
    print(
        f"OK: {args.saida.name} gerado "
        f"({len(relatorio.get('rejeicoes', []))} rejeicao(oes), "
        f"{len(relatorio.get('falhas', []))} falha(s))"
    )


if __name__ == "__main__":
    main()
