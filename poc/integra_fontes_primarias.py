#!/usr/bin/env python3
"""Integra a coleta de fontes primárias (releases/6-K/10-Q/ITR) ao JSON curado.

Entrada
    poc/coleta/<TICKER>.json   coleta por empresa: valores do trimestre, URL e linha de origem
    poc/ptax/raw.txt           PTAX diária de venda (Banco Central, boletim de fechamento)

Saída
    indicadores_oleo_gas.json  historico (1T25–1T26) e q_recente (2T26) substituídos pelos valores primários
    poc/contexto_mercado.json  bloco "ptax" (média e fechamento por trimestre, com a origem)

Regras
    * Pares: valores em US$ milhões, já na definição padronizada do 1T25 (ver README, "Definições").
    * Petrobras: valores originais em R$ milhões ficam gravados em "brl". Fluxos (receita, lucro,
      EBITDA, FCO, capex) são convertidos pela PTAX MÉDIA do trimestre; a dívida líquida, pela PTAX
      de FECHAMENTO do último dia útil. O script confere a dívida em US$ contra a divulgada pela
      companhia (tolerância de 0,5%).
    * Campos que a coleta não trouxe NÃO são preenchidos com o valor antigo do agregador: ficam
      como estão e a ausência é registrada em "pendencias".

Uso:  python3 poc/integra_fontes_primarias.py
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
POC = RAIZ / "poc"
DADOS = RAIZ / "indicadores_oleo_gas.json"
CONTEXTO = POC / "contexto_mercado.json"
CAMPOS = ["receita", "lucro_liquido", "ebitda", "fluxo_caixa_operacional", "capex", "fcf", "divida_liquida"]
PTAX_URL = ("https://ptax.bcb.gov.br/ptax_internet/consultaBoletim.do?method=consultarBoletim"
            "&RadOpcao=1&ChkMoeda=61&DATAINI=<início>&DATAFIM=<fim>")


def _linha(v):
    return json.dumps(v, ensure_ascii=False, separators=(", ", ": "))


def grava_json(dados, caminho=DADOS):
    """Grava no formato do arquivo vivo: um bloco por linha dentro de cada empresa.

    update_market_data.py reescreve o bloco "mercado" de forma cirúrgica e depende deste formato
    (tests/test_update_market.py::test_formato_do_arquivo_vivo_suporta_escrita_cirurgica)."""
    ref = json.dumps({"referencia": dados["referencia"]}, ensure_ascii=False, indent=2)[1:-1].strip("\n")
    blocos = []
    for e in dados["empresas"]:
        ls = ["    {", f'      "ticker": {_linha(e["ticker"])}, "nome": {_linha(e["nome"])}, "pais": {_linha(e["pais"])},']
        resto = [k for k in e if k not in ("ticker", "nome", "pais")]
        for i, k in enumerate(resto):
            fim = "," if i < len(resto) - 1 else ""
            if k == "historico":
                itens = [f"        {_linha(h)}" for h in e[k]]
                ls.append('      "historico": [\n' + ",\n".join(itens) + "\n      ]" + fim)
            else:
                ls.append(f'      "{k}": {_linha(e[k])}{fim}')
        ls.append("    }")
        blocos.append("\n".join(ls))
    texto = "{\n" + ref + ',\n  "empresas": [\n' + ",\n".join(blocos) + "\n  ]\n}\n"
    assert json.loads(texto) == dados
    caminho.write_text(texto, encoding="utf-8")


def ptax():
    q = collections.defaultdict(list)
    for linha in (POC / "ptax" / "raw.txt").read_text(encoding="utf-8").split():
        d, v = linha.split(";")
        dd, mm, aa = d.split("/")
        q[f"{aa}-Q{(int(mm) - 1) // 3 + 1}"].append((f"{aa}-{mm}-{dd}", float(v.replace(",", "."))))
    out = {}
    for p, dias in sorted(q.items()):
        dias.sort()
        out[p] = dict(media=round(sum(v for _, v in dias) / len(dias), 4), fechamento=dias[-1][1],
                      data_fechamento=dias[-1][0], dias_uteis=len(dias))
    return out


def primeira_url(v):
    u = v.get("fonte_url") or ""
    if isinstance(u, list):
        u = u[0] if u else ""
    return u.split(" ; ")[0].strip()


def main():
    dados = json.loads(DADOS.read_text(encoding="utf-8"))
    px = ptax()
    ctx = json.loads(CONTEXTO.read_text(encoding="utf-8"))
    ctx["ptax"] = dict(
        fonte="Banco Central do Brasil — PTAX de venda (boletim de fechamento), média aritmética dos dias úteis do trimestre",
        url=PTAX_URL, arquivo_diario="poc/ptax/raw.txt", coletado_em="2026-10-02",
        uso="Petrobras: fluxos pela média do trimestre; dívida líquida pela taxa de fechamento do último dia útil",
        trimestres=px)
    CONTEXTO.write_text(json.dumps(ctx, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    relatorio = []
    for e in dados["empresas"]:
        t = e["ticker"]
        arq = POC / "coleta" / f"{t}.json"
        if not arq.exists():
            continue
        col = json.loads(arq.read_text(encoding="utf-8"))
        linhas = {h["periodo"]: h for h in e["historico"]}
        q = e["q_recente"]
        tri, ano = q["trimestre"].split()
        linhas[f"{ano}-{tri}"] = q
        urls = {}
        for p, v in col["trimestres"].items():
            if p not in linhas:
                continue
            alvo = linhas[p]
            if t == "PBR":
                c = px[p]
                brl = {k: v.get(k) for k in ("receita_brl", "lucro_liquido_brl", "ebitda_brl", "ebitda_ajustado_brl",
                                             "ebitda_ajustado_sem_eventos_exclusivos_brl", "fco_brl", "capex_brl",
                                             "divida_liquida_brl")}
                novo = dict(receita=brl["receita_brl"] / c["media"], lucro_liquido=brl["lucro_liquido_brl"] / c["media"],
                            ebitda=brl["ebitda_brl"] / c["media"], fluxo_caixa_operacional=brl["fco_brl"] / c["media"],
                            capex=-brl["capex_brl"] / c["media"], divida_liquida=brl["divida_liquida_brl"] / c["fechamento"])
                novo["fcf"] = novo["fluxo_caixa_operacional"] + novo["capex"]
                novo = {k: round(x) for k, x in novo.items()}
                dif = novo["divida_liquida"] / v["divida_liquida_usd"] - 1
                if abs(dif) > 0.005:
                    raise SystemExit(f"PBR {p}: dívida em US$ pela PTAX de fechamento ({novo['divida_liquida']}) difere "
                                     f"{dif:+.2%} da divulgada ({v['divida_liquida_usd']})")
                # fora de historico/q_recente: esses blocos são "planos" (update_fundamentals.py reescreve
                # q_recente por regex e não aceita objetos aninhados)
                e.setdefault("conversao_brl", {})[p] = dict(
                    brl=brl, cambio=dict(ptax_media=c["media"], ptax_fechamento=c["fechamento"],
                                         divida_usd_divulgada=v["divida_liquida_usd"]))
            else:
                novo = {k: v.get(k) for k in CAMPOS}
            for k in CAMPOS:
                if novo.get(k) is None:
                    relatorio.append(f"{t} {p}: {k} ausente na coleta — mantido {alvo.get(k)}")
                    continue
                antes = alvo.get(k)
                alvo[k] = novo[k]
                if antes not in (None, 0) and abs(novo[k] / antes - 1) > 0.02:
                    relatorio.append(f"{t} {p} {k}: {antes:,} → {novo[k]:,}")
            if "margem_liquida_pct" in alvo and alvo.get("receita"):
                alvo["margem_liquida_pct"] = round(alvo["lucro_liquido"] / alvo["receita"] * 100, 2)
            alvo["fonte_dado"] = f"release oficial (primária) — {v.get('fonte_documento') or 'ver poc/coleta/' + t + '.json'}"[:300]
            urls[p] = primeira_url(v)
        e["proveniencia"]["fundamentos"] = dict(
            fonte="Releases/demonstrações oficiais da empresa (primária), definição padronizada idêntica à do 1T25",
            coletado_em="2026-10-02", detalhe=f"poc/coleta/{t}.json (URL, linha de origem e componentes por trimestre)",
            urls_por_trimestre=urls,
            campos_ainda_do_agregador=["divida_patrimonio_pct", "roe_pct", "roa_pct"])
        # Efetivo confirmado em documento da própria empresa (10-K, 20-F, URD, ESG datasheet)
        ef = json.loads((POC / "coleta" / "efetivo.json").read_text(encoding="utf-8")) if (POC / "coleta" / "efetivo.json").exists() else {}
        if t in ef and ef[t].get("confirmado"):
            x = ef[t]
            urls_ef = [u.strip() for u in x["fonte"].split(";")]
            e["efetivo"].update({"2024-12-31": x["2024-12-31"], "2025-12-31": x["2025-12-31"], "fonte": urls_ef[0],
                                 "fonte_primaria": True, "observacao": (x.get("documento") or "")[:160],
                                 "perimetro": (x.get("perimetro") or e["efetivo"].get("perimetro", ""))[:160]})
            if len(urls_ef) > 1:
                e["efetivo"]["fonte_complementar"] = urls_ef[1]
        # FY2025 e 4T25 têm a mesma data-base (31/12/2025): a dívida anual passa a ser a do release do 4T25.
        if linhas.get("2025-Q4", {}).get("divida_liquida") is not None:
            e["fy2025"]["divida_liquida"] = linhas["2025-Q4"]["divida_liquida"]

    ref = dados["referencia"]
    ref["versao_dados"] = "1.4"
    ref["fonte_principal"] = ("Releases, 6-K/8-K/10-Q e ITR das próprias empresas para a série trimestral 1T25–2T26 "
                              "(poc/coleta/); stockanalysis.com para os totais FY2025 e métricas de mercado")
    nota = ("Revisão 02/10/2026 (v1.4) — série trimestral 2T25–2T26 substituída por fontes primárias, na mesma definição "
            "do 1T25. Petrobras: fluxos pela PTAX média e dívida pela PTAX de fechamento (Banco Central). "
            "Equinor 1T26: dívida líquida corrigida de 4.209 para 11.761 (6-K de 06/05/2026).")
    if nota not in ref["notas"]:
        ref["notas"].append(nota)
    ref["notas"] = [n for n in ref["notas"] if not n.startswith("Petrobras: demonstrações originais em BRL")]
    ref["notas"].insert(0, "Petrobras: demonstrações originais em R$ (gravadas em 'brl' por trimestre). Fluxos convertidos "
                           "pela PTAX média do trimestre e dívida líquida pela PTAX de fechamento (Banco Central; "
                           "poc/contexto_mercado.json, bloco 'ptax').")
    grava_json(dados)
    print("\n".join(relatorio))
    print(f"{len(relatorio)} alterações materiais (>2%) registradas")


if __name__ == "__main__":
    main()
