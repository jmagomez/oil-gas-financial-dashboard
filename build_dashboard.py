#!/usr/bin/env python3
"""
Gera dashboard_oleo_gas.html a partir de:
  - dashboard_template.html   (esqueleto estático + placeholder __DATA_JSON__)
  - indicadores_oleo_gas.json (dados primários — fonte única de verdade)

Uso:
    python3 build_dashboard.py

O script:
  1. carrega o JSON primário;
  2. calcula uma camada de INDICADORES DERIVADOS (margem EBITDA, ND/EBITDA,
     conversão de FCF, capex/FCO, receita e EBITDA por boe, EV, EV por boe/d,
     FCF yield, cobertura de dividendos pelo FCF, run-rate trimestral e scores
     normalizados de perfil) — cálculo feito UMA única vez, aqui, para que
     dashboard e CSV nunca divirjam;
  3. valida sanidade dos números;
  4. injeta o payload enriquecido no template e grava o HTML;
  5. regenera o CSV, agora incluindo as colunas derivadas.

Nenhum indicador derivado é escrito de volta no JSON primário: ele continua
contendo apenas dados de fonte.
"""
import calendar
import csv
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
JSON_PATH = BASE / "indicadores_oleo_gas.json"
TEMPLATE_PATH = BASE / "dashboard_template.html"
HTML_OUT_PATH = BASE / "dashboard_oleo_gas.html"
CSV_OUT_PATH = BASE / "indicadores_oleo_gas.csv"

# Dias por período, usados nos indicadores "por boe".
# O trimestre é derivado do rótulo (ver `dias_do_trimestre`): Q1 tem 90 dias
# (91 em ano bissexto), Q2 91, Q3 e Q4 92. Um valor fixo de 90 distorceria
# receita/EBITDA por boe em ~2% assim que o período virasse Q2 ou Q3.
DIAS_PERIODO = {"fy2025": 365, "q_recente": 90}
# Fator de anualização das métricas de fluxo.
FATOR_ANUAL = {"fy2025": 1, "q_recente": 4}


def dias_do_trimestre(rotulo: str) -> int:
    """Dias corridos do trimestre a partir de um rótulo como "Q1 2026"."""
    m = re.search(r"Q([1-4])\s*(\d{4})", str(rotulo or ""))
    if not m:
        return DIAS_PERIODO["q_recente"]
    tri, ano = int(m.group(1)), int(m.group(2))
    meses = range(3 * tri - 2, 3 * tri + 1)
    return sum(calendar.monthrange(ano, mes)[1] for mes in meses)


def dias_do_ano(rotulo: str) -> int:
    m = re.search(r"(\d{4})", str(rotulo or ""))
    return 366 if (m and calendar.isleap(int(m.group(1)))) else 365


# Campos aceitos em cada item de `historico`. A lista existe para pegar erro de
# digitacao no preenchimento manual: um "lucro_liq" viraria None em silencio e o
# grafico mostraria uma lacuna sem explicacao.
HIST_CAMPOS = {
    "receita", "lucro_liquido", "ebitda", "fluxo_caixa_operacional",
    "fcf", "capex", "divida_liquida", "producao_kboed",
}


CSV_HEADER = [
    "ticker", "nome", "pais", "periodo",
    "receita_musd", "lucro_liquido_musd", "ebitda_musd", "margem_liquida_pct",
    "margem_liquida_fonte_pct",
    "fco_musd", "fcf_musd", "capex_musd", "divida_liquida_musd",
    "divida_patrimonio_pct", "roe_pct", "roa_pct", "producao_kboed",
    "market_cap_musd", "pe", "ev_ebitda", "dividend_yield_pct", "preco_acao_usd",
    # --- derivados ---
    "margem_ebitda_pct", "nd_ebitda_x", "conversao_fcf_pct", "capex_fco_pct",
    "receita_por_boe_usd", "ebitda_por_boe_usd", "ev_musd", "ev_por_boed_usd",
    "fcf_yield_pct", "cobertura_dividendo_x", "payout_fcf_pct",
    # Sinaliza que a produção da linha é proxy do trimestre, e não do período.
    "producao_proxy",
]


# --------------------------------------------------------------------------- #
# Helpers numéricos tolerantes a None / zero
# --------------------------------------------------------------------------- #
def div(a, b):
    """Divisão segura: None se algum operando faltar ou o denominador for zero."""
    if a is None or b is None or b == 0:
        return None
    return a / b


def pct(a, b):
    r = div(a, b)
    return None if r is None else r * 100.0


def arred(v, casas=2):
    return None if v is None else round(v, casas)


# --------------------------------------------------------------------------- #
# Camada de indicadores derivados
# --------------------------------------------------------------------------- #
def derivar_periodo(empresa, period_key):
    """Indicadores derivados de um período (fy2025 ou q_recente)."""
    p = empresa[period_key]
    m = empresa["mercado"]
    if period_key == "q_recente":
        dias = dias_do_trimestre(p.get("trimestre"))
    else:
        dias = dias_do_ano(p.get("periodo") or "2025")
    fator = FATOR_ANUAL[period_key]

    receita = p.get("receita")
    ebitda = p.get("ebitda")
    fcf = p.get("fcf")
    fco = p.get("fluxo_caixa_operacional")
    capex = p.get("capex")
    nd = p.get("divida_liquida")
    market_cap = m.get("market_cap")

    # Produção: se o período não tiver produção informada, usa a do trimestre
    # mais recente como proxy (caso Equinor FY2025) e sinaliza.
    prod = p.get("producao_kboed")
    prod_proxy = False
    if prod is None:
        prod = empresa["q_recente"].get("producao_kboed")
        prod_proxy = prod is not None

    ebitda_anual = None if ebitda is None else ebitda * fator
    fcf_anual = None if fcf is None else fcf * fator

    # Barris de óleo equivalente no período (mil boe/d -> boe totais).
    boe_periodo = None if prod is None else prod * 1000.0 * dias
    # Barris/dia (para EV por boe/d).
    boed = None if prod is None else prod * 1000.0

    ev = None if (market_cap is None or nd is None) else market_cap + nd
    dividendos = div(
        None if market_cap is None else market_cap * (m.get("dividend_yield_pct") or 0.0),
        100.0,
    )

    return {
        # Margem líquida recalculada a partir dos campos primários. Ver
        # `consolidar_margem` para o porquê de ela substituir a da fonte.
        "margem_liquida_calc_pct": arred(pct(p.get("lucro_liquido"), receita)),
        "margem_ebitda_pct": arred(pct(ebitda, receita)),
        "ebitda_anualizado": arred(ebitda_anual, 0),
        "fcf_anualizado": arred(fcf_anual, 0),
        # Alavancagem: dívida líquida sobre EBITDA anualizado.
        "nd_ebitda_x": arred(div(nd, ebitda_anual)),
        # Quanto do EBITDA vira caixa livre.
        "conversao_fcf_pct": arred(pct(fcf, ebitda)),
        # Intensidade de reinvestimento.
        "capex_fco_pct": arred(pct(None if capex is None else abs(capex), fco)),
        # Valores em US$ milhões -> US$ por barril equivalente.
        "receita_por_boe_usd": arred(div(None if receita is None else receita * 1e6, boe_periodo)),
        "ebitda_por_boe_usd": arred(div(None if ebitda is None else ebitda * 1e6, boe_periodo)),
        "producao_proxy": prod_proxy,
        # Produção efetivamente usada nos indicadores por boe. Sem isso o CSV
        # mostrava a coluna de produção VAZIA ao lado de um US$/boe calculado
        # com o proxy do trimestre — quem lesse a planilha não teria como saber.
        "producao_usada_kboed": prod,
        "dias_periodo": dias,
        "ev": arred(ev, 0),
        # US$ de EV por barril/dia de produção — "quanto o mercado paga pela capacidade".
        "ev_por_boed_usd": arred(div(None if ev is None else ev * 1e6, boed), 0),
        # Retorno de caixa implícito sobre o valor de mercado.
        "fcf_yield_pct": arred(pct(fcf_anual, market_cap)),
        "dividendos_estimados": arred(dividendos, 0),
        # Quantas vezes o FCF cobre o dividendo estimado (>1 = dividendo pago com caixa próprio).
        "cobertura_dividendo_x": arred(div(fcf_anual, dividendos)),
        "payout_fcf_pct": arred(pct(dividendos, fcf_anual)),
    }


def derivar_empresa(empresa):
    """Indicadores derivados no nível da empresa (comparação entre períodos)."""
    fy, q = empresa["fy2025"], empresa["q_recente"]

    def run_rate(campo):
        """Trimestre anualizado vs. ano fiscal, em %."""
        anual = fy.get(campo)
        trimestral = q.get(campo)
        if anual in (None, 0) or trimestral is None:
            return None
        return arred((trimestral * 4 / anual - 1) * 100.0)

    return {
        "run_rate_receita_pct": run_rate("receita"),
        "run_rate_ebitda_pct": run_rate("ebitda"),
        "run_rate_lucro_pct": run_rate("lucro_liquido"),
        "run_rate_fcf_pct": run_rate("fcf"),
        "delta_divida_liquida": (
            None
            if (q.get("divida_liquida") is None or fy.get("divida_liquida") is None)
            else arred(q["divida_liquida"] - fy["divida_liquida"], 0)
        ),
        "delta_margem_liquida_pp": (
            None
            if (q.get("margem_liquida_pct") is None or fy.get("margem_liquida_pct") is None)
            else arred(q["margem_liquida_pct"] - fy["margem_liquida_pct"])
        ),
    }


def consolidar_margem(p):
    """Faz a margem exibida ser `lucro_liquido / receita`, e não a da fonte.

    As duas divergiam porque usam numeradores diferentes: a fonte calcula sobre o
    lucro CONSOLIDADO (incluindo não-controladores) e o campo lucro_liquido traz a
    parcela ATRIBUÍVEL AOS ACIONISTAS. Reconciliação confirmada no 6-K da própria
    BP para FY2025 (US$ milhões):

        Sales and other operating revenues .......  189.335
        Profit for the period ....................    1.295   -> 1.295/189.335 = 0,68%
        Less: Non-controlling interests ..........    1.240
        Profit attributable to bp shareholders ...       55   ->    55/189.335 = 0,03%

    O 0,68% que vinha da fonte é o lucro consolidado; os 0,03% são o que de fato
    sobra para o acionista. Como o dashboard mostra lucro_liquido e margem lado a
    lado, exibir os dois com numeradores diferentes era inconsistente. O valor
    original da fonte fica preservado em `margem_liquida_fonte_pct`.

    O JSON primário não é alterado: a troca acontece só no payload em memória.
    """
    p["margem_liquida_fonte_pct"] = p.get("margem_liquida_pct")
    calc = p["derivados"]["margem_liquida_calc_pct"]
    if calc is not None:
        p["margem_liquida_pct"] = calc


# Eixos do radar de perfil. maior_melhor=False inverte a normalização.
EIXOS_PERFIL = [
    ("Rentabilidade", lambda e: e["q_recente"]["derivados"]["margem_ebitda_pct"], True),
    ("Geração de caixa", lambda e: e["fy2025"]["derivados"]["conversao_fcf_pct"], True),
    ("Solidez", lambda e: e["fy2025"]["derivados"]["nd_ebitda_x"], False),
    ("Valuation", lambda e: e["mercado"]["ev_ebitda"], False),
    ("Retorno ao acionista", lambda e: e["mercado"]["dividend_yield_pct"], True),
    ("Escala", lambda e: e["q_recente"]["producao_kboed"], True),
]


def calcular_perfil(empresas):
    """Normaliza cada eixo em 0–100 (min-max) para o radar comparativo."""
    for nome, getter, maior_melhor in EIXOS_PERFIL:
        valores = [(e, getter(e)) for e in empresas]
        validos = [v for _, v in valores if v is not None]
        if not validos:
            for e, _ in valores:
                e.setdefault("perfil", {})[nome] = None
            continue
        lo, hi = min(validos), max(validos)
        span = hi - lo
        for e, v in valores:
            if v is None:
                score = None
            elif span == 0:
                score = 50.0
            else:
                score = (v - lo) / span * 100.0
                if not maior_melhor:
                    score = 100.0 - score
            e.setdefault("perfil", {})[nome] = arred(score, 1)


def enriquecer(data):
    """Adiciona a camada derivada ao payload em memória."""
    for e in data["empresas"]:
        for period_key in ("fy2025", "q_recente"):
            e[period_key]["derivados"] = derivar_periodo(e, period_key)
            consolidar_margem(e[period_key])
        e["derivados"] = derivar_empresa(e)
        e.setdefault("historico", [])
    calcular_perfil(data["empresas"])
    # Trimestre POR EMPRESA. Cada uma divulga na sua data, entao durante a
    # temporada de balancos e normal o arquivo ter empresas em trimestres
    # diferentes. O template lia o rotulo de empresas[0] e aplicava a todas,
    # o que anunciaria "Q2 2026" para quem ainda estivesse em Q1.
    trimestres = {e["ticker"]: e["q_recente"].get("trimestre") for e in data["empresas"]}
    data["meta_build"] = {
        "trimestres": trimestres,
        "trimestres_mistos": len(set(trimestres.values())) > 1,
        "eixos_perfil": [nome for nome, _, _ in EIXOS_PERFIL],
        "dias_periodo": DIAS_PERIODO,
        "fator_anualizacao": FATOR_ANUAL,
        "tem_historico": any(e.get("historico") for e in data["empresas"]),
    }
    return data


# --------------------------------------------------------------------------- #
# Validação
# --------------------------------------------------------------------------- #
def validate(data):
    """Checagens básicas de sanidade antes de publicar."""
    problems = []
    # Comparar empresas em trimestres diferentes e legitimo durante a temporada
    # de balancos, mas precisa estar declarado, nao implicito.
    tris = data.get("meta_build", {}).get("trimestres", {})
    if len(set(tris.values())) > 1:
        por_tri = {}
        for tk, tr in tris.items():
            por_tri.setdefault(tr, []).append(tk)
        detalhe = "; ".join(f"{tr}: {', '.join(sorted(tks))}" for tr, tks in sorted(por_tri.items()))
        problems.append(
            f"empresas em trimestres diferentes ({detalhe}) — a comparação entre "
            "elas mistura períodos; o dashboard sinaliza isso ao usuário"
        )
    for e in data["empresas"]:
        for period_key in ("fy2025", "q_recente"):
            p = e[period_key]
            if p["receita"] and p["lucro_liquido"] is not None:
                if abs(p["lucro_liquido"]) > p["receita"]:
                    problems.append(f"{e['ticker']} {period_key}: lucro líquido maior que receita")
            # Divergência entre a margem da fonte (lucro consolidado) e a
            # recalculada (lucro atribuível aos acionistas). Ver `consolidar_margem`.
            fonte = p.get("margem_liquida_fonte_pct")
            calc = p.get("margem_liquida_pct")
            if p["receita"] and fonte is not None and calc is not None and abs(fonte - calc) > 0.15:
                implicito = fonte / 100.0 * p["receita"]
                problems.append(
                    f"{e['ticker']} {period_key}: margem da fonte ({fonte:.2f}%) implica lucro de "
                    f"{implicito:,.0f} contra {p['lucro_liquido']:,.0f} atribuivel aos acionistas "
                    f"(diferenca de ~{implicito - p['lucro_liquido']:,.0f}, compativel com "
                    f"nao-controladores; o implicito e aproximado por vir da margem arredondada). "
                    f"Exibindo a margem recalculada, {calc:.2f}%"
                )
            if p["ebitda"] and p["receita"] and p["ebitda"] > p["receita"] * 1.5:
                problems.append(f"{e['ticker']} {period_key}: EBITDA muito acima da receita (checar unidade/escala)")
            d = p.get("derivados", {})
            if d.get("margem_ebitda_pct") is not None and d["margem_ebitda_pct"] > 100:
                problems.append(f"{e['ticker']} {period_key}: margem EBITDA acima de 100%")
            if d.get("nd_ebitda_x") is not None and d["nd_ebitda_x"] > 4:
                problems.append(
                    f"{e['ticker']} {period_key}: ND/EBITDA de {d['nd_ebitda_x']}x — alavancagem alta para o setor"
                )
            if d.get("cobertura_dividendo_x") is not None and d["cobertura_dividendo_x"] < 1:
                problems.append(
                    f"{e['ticker']} {period_key}: FCF não cobre o dividendo estimado "
                    f"({d['cobertura_dividendo_x']}x)"
                )
            if d.get("producao_proxy"):
                problems.append(
                    f"{e['ticker']} {period_key}: produção ausente — indicadores por boe usam proxy do trimestre"
                )
        m = e["mercado"]
        if m["pe"] and m["pe"] < 0:
            problems.append(f"{e['ticker']}: P/E negativo (ok se prejuízo, mas confirmar)")
        if not e.get("fontes"):
            problems.append(f"{e['ticker']}: sem fontes listadas")
        if not e["q_recente"].get("trimestre"):
            problems.append(f"{e['ticker']}: q_recente sem rótulo 'trimestre'")
        # `historico` e preenchido a mao. Estas checagens existem para o erro
        # aparecer no build, e nao como uma lacuna silenciosa no grafico.
        vistos = set()
        for h in e.get("historico", []):
            per = h.get("periodo")
            if not per:
                problems.append(f"{e['ticker']}: item de histórico sem campo 'periodo'")
                continue
            if not re.fullmatch(r"FY\d{4}", str(per)):
                problems.append(
                    f"{e['ticker']} histórico: período {per!r} fora do formato FY####"
                )
            if per in vistos:
                problems.append(f"{e['ticker']} histórico: período {per} duplicado")
            vistos.add(per)

            desconhecidos = set(h) - HIST_CAMPOS - {"periodo"}
            if desconhecidos:
                problems.append(
                    f"{e['ticker']} histórico {per}: campo(s) não reconhecido(s) "
                    f"{sorted(desconhecidos)} — erro de digitação?"
                )
            for campo in HIST_CAMPOS & set(h):
                v = h[campo]
                if v is not None and not isinstance(v, (int, float)):
                    problems.append(
                        f"{e['ticker']} histórico {per}: {campo} não é numérico ({v!r})"
                    )
            # capex é armazenado negativo no resto do arquivo; manter a convenção
            if isinstance(h.get("capex"), (int, float)) and h["capex"] > 0:
                problems.append(
                    f"{e['ticker']} histórico {per}: capex positivo ({h['capex']}) — "
                    "no resto do arquivo capex é negativo"
                )
            rec, luc, eb = h.get("receita"), h.get("lucro_liquido"), h.get("ebitda")
            if isinstance(rec, (int, float)) and rec and isinstance(luc, (int, float)):
                if abs(luc) > rec:
                    problems.append(f"{e['ticker']} histórico {per}: |lucro| maior que a receita")
            if isinstance(rec, (int, float)) and rec and isinstance(eb, (int, float)):
                if eb > rec * 1.5:
                    problems.append(
                        f"{e['ticker']} histórico {per}: EBITDA muito acima da receita "
                        "(checar unidade/escala)"
                    )
    return problems


# --------------------------------------------------------------------------- #
# Saídas
# --------------------------------------------------------------------------- #
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
            d = p["derivados"]
            rows.append([
                e["ticker"], e["nome"], e["pais"], label,
                p["receita"], p["lucro_liquido"], p["ebitda"], p["margem_liquida_pct"],
                p.get("margem_liquida_fonte_pct"),
                p["fluxo_caixa_operacional"], p["fcf"], p["capex"], p["divida_liquida"],
                p["divida_patrimonio_pct"], p["roe_pct"], p["roa_pct"],
                p["derivados"]["producao_usada_kboed"],
                e["mercado"]["market_cap"], e["mercado"]["pe"], e["mercado"]["ev_ebitda"],
                e["mercado"]["dividend_yield_pct"], e["mercado"]["preco_acao"],
                d["margem_ebitda_pct"], d["nd_ebitda_x"], d["conversao_fcf_pct"], d["capex_fco_pct"],
                d["receita_por_boe_usd"], d["ebitda_por_boe_usd"], d["ev"], d["ev_por_boed_usd"],
                d["fcf_yield_pct"], d["cobertura_dividendo_x"], d["payout_fcf_pct"],
                "sim" if d["producao_proxy"] else "nao",
            ])
    # lineterminator="\n": o padrão do módulo csv é \r\n, o que deixava o
    # arquivo com CRLF e o diff sensível à plataforma. Com LF explícito o build
    # é idempotente e a rotina diária só comita quando um número muda de fato.
    with CSV_OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CSV_HEADER)
        w.writerows(rows)
    print(f"OK: {CSV_OUT_PATH.name} gerado ({len(rows)} linhas, {len(CSV_HEADER)} colunas)")


def main():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    data = enriquecer(data)

    problems = validate(data)
    if problems:
        print("AVISOS de validação (não bloqueantes):")
        for p in problems:
            print(f"  - {p}")

    build_html(data)
    build_csv(data)


if __name__ == "__main__":
    main()
