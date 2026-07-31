#!/usr/bin/env python3
"""Gera o corpo HTML do e-mail diario da rotina de dados de mercado.

Le o relatorio produzido por update_market_data.py (--relatorio) e o JSON
primario, e monta um resumo do pregao. Reaproveita build_dashboard para a
camada derivada e para a validacao, de modo que e-mail, dashboard e CSV nunca
divirjam.

Uso:
    python3 build_email.py --relatorio caminho/relatorio-mercado.json
"""
import argparse
import datetime as dt
import html
import json
from pathlib import Path

import build_dashboard as bd

BASE = Path(__file__).resolve().parent
OUT = BASE / "email_body.html"

# Rotulos e formatacao das colunas do quadro de mercado.
CAMPOS = [
    ("preco_acao", "Preço (US$)", 2),
    ("market_cap", "Market cap (US$ mi)", 0),
    ("pe", "P/E", 2),
    ("ev_ebitda", "EV/EBITDA", 2),
    ("dividend_yield_pct", "Div. yield (%)", 2),
]


def num(v, casas=2):
    """Formata no padrao brasileiro: 1.234,56."""
    if v is None:
        return "—"
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


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
        "padding:10px 12px;border-radius:6px;margin:0 0 14px;font-size:13px;line-height:1.6'>"
        "<b>Atenção: valores não aceitos nesta execução.</b><br>"
        "O valor anterior foi mantido — nada suspeito é gravado por cima de um número bom.<br><br>"
        + "<br>".join(linhas)
        + "</div>"
    )


def bloco_mudancas(relatorio):
    mud = sorted(relatorio.get("mudancas", []), key=lambda x: (x["ticker"], x["campo"]))
    if not mud:
        return "<p style='color:#666;font-size:13px'>Nenhum campo de mercado mudou nesta execução.</p>"
    linhas = []
    for m in mud:
        var = ""
        if m.get("var_pct") is not None:
            cor = "#0a7a2f" if m["var_pct"] >= 0 else "#c0392b"
            var = f" <span style='color:{cor}'>({m['var_pct']:+.2f}%)</span>".replace(".", ",")
        casas = 0 if m["campo"] == "market_cap" else 2
        antes = num(m["antes"], casas) if isinstance(m["antes"], (int, float)) else str(m["antes"])
        depois = num(m["depois"], casas) if isinstance(m["depois"], (int, float)) else str(m["depois"])
        linhas.append(
            f"<li style='margin-bottom:3px'><b>{html.escape(m['ticker'])}</b> "
            f"{html.escape(m['campo'])}: {html.escape(antes)} → "
            f"<b>{html.escape(depois)}</b>{var}</li>"
        )
    return (
        f"<h3 style='font-size:14px;margin:18px 0 6px'>O que mudou ({len(mud)})</h3>"
        f"<ul style='margin:0;padding-left:20px;font-size:13px;color:#333'>{''.join(linhas)}</ul>"
    )


def bloco_tabela(data, variacoes):
    cab = "".join(
        f"<th style='padding:6px 10px;text-align:right'>{html.escape(rot)}</th>"
        for _, rot, _ in CAMPOS
    )
    linhas = []
    for e in data["empresas"]:
        m = e["mercado"]
        v = variacoes.get(e["ticker"])
        cor = "#666" if v is None else ("#0a7a2f" if v >= 0 else "#c0392b")
        vtxt = "—" if v is None else f"{v:+.2f}%".replace(".", ",")
        celulas = "".join(
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;text-align:right'>"
            f"{num(m.get(c), casas)}</td>"
            for c, _, casas in CAMPOS
        )
        linhas.append(
            f"<tr><td style='padding:6px 10px;border-bottom:1px solid #eee'>"
            f"<b>{html.escape(e['ticker'])}</b> "
            f"<span style='color:#999;font-size:12px'>{html.escape(e['nome'])}</span></td>"
            f"{celulas}"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;text-align:right;color:{cor}'>"
            f"{vtxt}</td></tr>"
        )
    return (
        "<table style='border-collapse:collapse;width:100%;font-size:13px'>"
        f"<tr style='background:#f5f5f5'><th style='padding:6px 10px;text-align:left'>Empresa</th>"
        f"{cab}<th style='padding:6px 10px;text-align:right'>Var. dia</th></tr>"
        + "".join(linhas)
        + "</table>"
    )


def bloco_validacao(problemas):
    if not problemas:
        return ""
    # Nada de <details>: Gmail e boa parte dos clientes removem a tag e o
    # conteudo aparece sempre expandido ou some. Bloco simples e discreto.
    itens = "".join(f"<li style='margin-bottom:3px'>{html.escape(p)}</li>" for p in problemas)
    return (
        "<div style='margin-top:18px;padding:10px 12px;background:#f7f7f7;"
        "border-left:3px solid #d0d0d0;border-radius:4px'>"
        f"<div style='font-size:13px;color:#555;font-weight:bold;margin-bottom:6px'>"
        f"Avisos de validação dos dados ({len(problemas)})</div>"
        f"<ul style='margin:0;padding-left:18px;font-size:12px;color:#666;line-height:1.5'>{itens}</ul>"
        "</div>"
    )


def montar(relatorio, data, pages_url=""):
    variacoes = var_por_ticker(relatorio)
    problemas = bd.validate(data)
    ref = data.get("referencia", {})
    consulta = ref.get("data_consulta", "—")
    gerado = relatorio.get("gerado_em", dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
    link = (
        f"<p style='margin-top:16px'><a href='{html.escape(pages_url)}' style='color:#1a56db'>"
        "Abrir dashboard completo</a></p>"
        if pages_url
        else ""
    )
    return f"""
<div style="font-family:Arial,Helvetica,sans-serif;max-width:720px">
  <h2 style="margin-bottom:4px">Óleo &amp; Gás — dados de mercado</h2>
  <p style="color:#666;margin-top:0;font-size:13px">
    Preço, market cap, P/E, EV/EBITDA e dividend yield das 7 majors, atualizados após o
    fechamento de Nova York. Os fundamentos (receita, EBITDA, capex, dívida, produção)
    são curados a cada balanço e não mudam nesta rotina — referência atual: {html.escape(str(consulta))}.
  </p>
  {bloco_alertas(relatorio)}
  {bloco_tabela(data, variacoes)}
  {bloco_mudancas(relatorio)}
  {bloco_validacao(problemas)}
  {link}
  <p style="color:#999;font-size:12px;margin-top:14px">
    Gerado automaticamente em {html.escape(str(gerado))} · fonte de mercado: Yahoo Finance.
    Uso informativo, não é recomendação de investimento.
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
        f"({len(relatorio.get('mudancas', []))} mudanca(s), "
        f"{len(relatorio.get('rejeicoes', []))} rejeicao(oes), "
        f"{len(relatorio.get('falhas', []))} falha(s))"
    )


if __name__ == "__main__":
    main()
