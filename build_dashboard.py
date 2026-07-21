#!/usr/bin/env python3
"""
Gera dashboard_oleo_gas.html a partir de:
  - dashboard_template.html  (esqueleto estático + placeholder __DATA_JSON__)
  - indicadores_oleo_gas.json (dados)

Uso:
    python3 build_dashboard.py

Também regenera indicadores_oleo_gas.csv a partir do mesmo JSON, para manter
as duas representações (planilha e dashboard) sempre sincronizadas com uma
única fonte de verdade.

Isso substitui o processo manual anterior (editar o HTML com um placeholder
e injetar o JSON via sed/python ad-hoc a cada atualização).
"""
import csv
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
JSON_PATH = BASE / "indicadores_oleo_gas.json"
TEMPLATE_PATH = BASE / "dashboard_template.html"
HTML_OUT_PATH = BASE / "dashboard_oleo_gas.html"
CSV_OUT_PATH = BASE / "indicadores_oleo_gas.csv"

CSV_HEADER = [
    "ticker", "nome", "pais", "periodo",
    "receita_musd", "lucro_liquido_musd", "ebitda_musd", "margem_liquida_pct",
    "fco_musd", "fcf_musd", "capex_musd", "divida_liquida_musd",
    "divida_patrimonio_pct", "roe_pct", "roa_pct", "producao_kboed",
    "market_cap_musd", "pe", "ev_ebitda", "dividend_yield_pct", "preco_acao_usd",
]


def validate(data):
    """Checagens básicas de sanidade antes de publicar."""
    problems = []
    for e in data["empresas"]:
        for period_key in ("fy2025", "q_recente"):
            p = e[period_key]
            if p["receita"] and p["lucro_liquido"] is not None:
                if abs(p["lucro_liquido"]) > p["receita"]:
                    problems.append(f"{e['ticker']} {period_key}: lucro líquido maior que receita")
            if p["ebitda"] and p["receita"] and p["ebitda"] > p["receita"] * 1.5:
                problems.append(f"{e['ticker']} {period_key}: EBITDA muito acima da receita (checar unidade/escala)")
        m = e["mercado"]
        if m["pe"] and m["pe"] < 0:
            problems.append(f"{e['ticker']}: P/E negativo (ok se prejuízo, mas confirmar)")
        if not e.get("fontes"):
            problems.append(f"{e['ticker']}: sem fontes listadas")
    return problems


def build_html(data):
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False)
    if "__DATA_JSON__" not in template:
        sys.exit("ERRO: placeholder __DATA_JSON__ não encontrado no template.")
    html = template.replace("__DATA_JSON__", payload)
    HTML_OUT_PATH.write_text(html, encoding="utf-8")
    print(f"OK: {HTML_OUT_PATH.name} gerado ({len(html):,} bytes)")


def build_csv(data):
    rows = []
    for e in data["empresas"]:
        for period_key, label in (("fy2025", "FY2025"), ("q_recente", e["q_recente"]["trimestre"])):
            p = e[period_key]
            rows.append([
                e["ticker"], e["nome"], e["pais"], label,
                p["receita"], p["lucro_liquido"], p["ebitda"], p["margem_liquida_pct"],
                p["fluxo_caixa_operacional"], p["fcf"], p["capex"], p["divida_liquida"],
                p["divida_patrimonio_pct"], p["roe_pct"], p["roa_pct"], p.get("producao_kboed"),
                e["mercado"]["market_cap"], e["mercado"]["pe"], e["mercado"]["ev_ebitda"],
                e["mercado"]["dividend_yield_pct"], e["mercado"]["preco_acao"],
            ])
    with CSV_OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        w.writerows(rows)
    print(f"OK: {CSV_OUT_PATH.name} gerado ({len(rows)} linhas)")


def main():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    problems = validate(data)
    if problems:
        print("AVISOS de validação (não bloqueantes):")
        for p in problems:
            print(f"  - {p}")

    build_html(data)
    build_csv(data)


if __name__ == "__main__":
    main()
