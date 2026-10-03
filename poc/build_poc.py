#!/usr/bin/env python3
"""PoC — benchmarking financeiro trimestral Petrobras vs. pares.

Le a fonte unica de verdade do repositorio (indicadores_oleo_gas.json), aplica
as regras de qualidade R1-R8, calcula os 6 indicadores da PoC por empresa e
trimestre e publica:

    poc/poc_data.json               payload do painel (fato + log de QA + dimensoes)
    poc/fato_indicador.csv          tabela longa (1 linha por empresa x periodo x indicador)
    poc/dim_*.csv                   dimensoes (empresa, periodo, indicador, fonte)
    poc/qa_log.csv                  alertas de qualidade
    poc/painel_benchmarking_poc.html painel autocontido (template + payload)

Uso:
    python3 poc/build_poc.py            # gera tudo
    python3 poc/build_poc.py --check    # so roda o QA e falha se houver vermelho novo nao tratado

Principios
----------
* Nenhum valor e "corrigido" aqui: correcoes vao para o JSON curado, com nota.
  Esta camada so mede, sinaliza e decide o que entra em ranking/mediana.
* Vermelho = erro provavel de dado (sai de rankings, medianas e linhas).
  Amarelo = requer leitura (exibido com marcador). Alerta explicado pelo
  contexto (Brent) fica registrado, mas nao rebaixa o valor.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import json
import re
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
POC = RAIZ / "poc"
JSON_DADOS = RAIZ / "indicadores_oleo_gas.json"
SNAPSHOT = RAIZ / "tests" / "fixtures" / "indicadores_snapshot.json"

JANELA = 6  # trimestres exibidos; um trimestre novo entra sozinho e o mais antigo sai


def _fim(p):
    ano, q = int(p[:4]), int(p[-1])
    return date(ano, q * 3, calendar.monthrange(ano, q * 3)[1])


def _dias(p):
    ini = date(int(p[:4]), int(p[-1]) * 3 - 2, 1)
    return (_fim(p) - ini).days + 1


def periodos_da_base(base):
    todos = sorted({p for linhas in base.values() for p in linhas if len(p) == 7 and p[4:6] == "-Q"})
    return todos[-JANELA:]


# Brent medio trimestral (FRED/IMF, serie POILBREUSDQ) -- contexto para a regra R5.
CONTEXTO = POC / "contexto_mercado.json"
BRENT = {k: v for k, v in json.loads(CONTEXTO.read_text(encoding="utf-8"))["brent_medio_usd_bbl"].items()} if CONTEXTO.exists() else {}
PTAX = json.loads(CONTEXTO.read_text(encoding="utf-8")).get("ptax", {}) if CONTEXTO.exists() else {}
# Leituras de release que explicam alertas (poc/leituras.json): fecham o alerta sem alterar o valor.
LEITURAS = json.loads((POC / "leituras.json").read_text(encoding="utf-8"))["leituras"] if (POC / "leituras.json").exists() else []
PERIODOS: list[str] = []
ROTULO: dict[str, str] = {}
DIAS: dict[str, int] = {}
FIM: dict[str, str] = {}


def define_periodos(base):
    global PERIODOS
    PERIODOS = periodos_da_base(base)
    for p in PERIODOS:
        ROTULO[p] = f"{p[-1]}T{p[2:4]}"
        DIAS[p] = _dias(p)
        FIM[p] = _fim(p).isoformat()
    return PERIODOS


POC_EMPRESAS = ["PBR", "XOM", "SHEL", "EQNR"]
ORDEM_EMPRESAS = ["PBR", "XOM", "SHEL", "EQNR", "CVX", "BP", "TTE"]
PERFIL = {
    "PBR": ("Petrobras", "Brasil", "IFRS", "Estatal de capital aberto; upstream pré-sal + refino"),
    "XOM": ("ExxonMobil", "EUA", "US GAAP", "Integrada global; sócia em Bacalhau"),
    "SHEL": ("Shell", "Reino Unido", "IFRS", "Integrada; GNL; maior produtora estrangeira no Brasil"),
    "EQNR": ("Equinor", "Noruega", "IFRS", "Controle estatal; offshore; operadora de Bacalhau"),
    "CVX": ("Chevron", "EUA", "US GAAP", "Integrada (escala)"),
    "BP": ("BP", "Reino Unido", "IFRS", "Integrada (escala)"),
    "TTE": ("TotalEnergies", "França", "IFRS", "Integrada (escala)"),
}

INDICADORES = [
    # codigo, nome, unidade, direcao (1 = maior melhor, -1 = menor melhor, 0 = contexto), casas, formula, grupo
    ("margem_ebitda", "Margem EBITDA", "%", 1, 1, "EBITDA ÷ receita do trimestre", "core"),
    ("margem_liquida", "Margem líquida", "%", 1, 1, "Lucro líquido atribuível ÷ receita", "core"),
    ("fcf", "Fluxo de caixa livre", "US$ bi", 1, 1, "FCO + capex (capex com sinal negativo)", "core"),
    ("nd_ebitda", "Dívida líquida / EBITDA", "x", -1, 2,
     "Dívida líquida (incl. arrendamentos) no fim do trimestre ÷ EBITDA dos últimos 12 meses (×4 do trimestre quando a janela TTM não existe)", "core"),
    ("ebitda_boe", "EBITDA por boe", "US$/boe", 1, 1, "EBITDA ÷ (produção kboe/d × dias do trimestre)", "core"),
    ("efetivo", "Total de efetivo", "empregados", 0, 0,
     "Empregados no fim do exercício (divulgação anual); trimestres seguintes repetem o último valor divulgado", "core"),
    ("ebitda_por_empregado", "EBITDA TTM por empregado", "US$ mil", 1, 0,
     "EBITDA dos últimos 12 meses ÷ efetivo do fim do exercício mais recente", "complementar"),
]
IND = {i[0]: i for i in INDICADORES}

# Insumos de cada indicador -- o status do indicador herda o pior status dos insumos.
INSUMOS = {
    "margem_ebitda": ["ebitda", "receita"],
    "margem_liquida": ["lucro_liquido", "receita"],
    "fcf": ["fcf", "fluxo_caixa_operacional", "capex"],
    "nd_ebitda": ["divida_liquida", "ebitda"],
    "ebitda_boe": ["ebitda", "producao_kboed"],
    "efetivo": [],
    "ebitda_por_empregado": ["ebitda"],
}
OBRIGATORIOS = ["receita", "lucro_liquido", "ebitda", "fluxo_caixa_operacional", "fcf", "capex",
                "divida_liquida", "producao_kboed"]
ELASTICIDADE_MAX = 3.0  # R5: variação justificada pelo Brent até 3× a variação do Brent
LIMITE_FCF = 0.5        # R4: |ΔFCF| acima de 50% do EBITDA do trimestre anterior
LIMITES_VAR = {"receita": 0.30, "ebitda": 0.40, "lucro_liquido": 0.60}
SEV_ORD = {"verde": 0, "amarelo": 1, "vermelho": 2}


def carrega(caminho=JSON_DADOS):
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    empresas = {e["ticker"]: e for e in dados["empresas"]}
    base = {}
    for t, e in empresas.items():
        q = dict(e["q_recente"])
        tri, ano = q.get("trimestre", "Q0 0000").split()
        q["periodo"] = f"{ano}-{tri}"
        linhas = {h["periodo"]: h for h in e.get("historico", [])}
        linhas[q["periodo"]] = q
        for p, conv in (e.get("conversao_brl") or {}).items():  # Petrobras: valores em R$ e câmbio usado
            if p in linhas:
                linhas[p] = {**linhas[p], **conv}
        base[t] = linhas
    define_periodos(base)
    return dados, empresas, base


# --------------------------------------------------------------------------- #
# Regras de qualidade
# --------------------------------------------------------------------------- #
class Log:
    def __init__(self):
        self.itens = []

    def add(self, t, p, campo, regra, sev, msg, justificado=False):
        msg = re.sub(r"(\d),(\d{3})", r"\1.\2", re.sub(r"(\d),(\d{3})", r"\1.\2", msg))  # milhar pt-BR
        self.itens.append(dict(empresa=t, periodo=p, campo=campo, regra=regra, severidade=sev,
                               justificado=justificado, mensagem=msg, leitura="", fonte_leitura=""))

    def aplica_leituras(self, leituras):
        """Fecha alertas amarelos com uma leitura de release (mesma empresa, período e campo).

        A leitura não muda o valor: registra por que a variação é real e como usá-la na análise.
        Vermelho (erro provável de dado) nunca é fechado por leitura."""
        usadas = set()
        for x in self.itens:
            for k, lt in enumerate(leituras):
                if (lt["empresa"], lt["periodo"], lt["campo"]) == (x["empresa"], x["periodo"], x["campo"]) \
                        and x["severidade"] == "amarelo" and x["regra"].startswith("R4"):
                    usadas.add(k)
                    x["leitura"] = f"{lt['explicacao']} Implicação: {lt['implicacao']}"
                    x["fonte_leitura"] = lt["fonte_url"]
                    if not x["justificado"]:
                        x["justificado"] = True
                        x["mensagem"] += " — explicado pelo release (ver leitura)"
        return usadas

    def status_campo(self, t, p, campo):
        pior = "verde"
        for x in self.itens:
            if x["empresa"] == t and x["periodo"] == p and x["campo"] == campo and not x["justificado"]:
                if SEV_ORD[x["severidade"]] > SEV_ORD[pior]:
                    pior = x["severidade"]
        return pior


def aplica_regras(dados, empresas, base):
    log = Log()
    snap = {e["ticker"]: e for e in json.loads(SNAPSHOT.read_text(encoding="utf-8"))["empresas"]} if SNAPSHOT.exists() else {}
    for t in ORDEM_EMPRESAS:
        R = base[t]
        for i, p in enumerate(PERIODOS):
            r = R.get(p)
            if r is None:
                log.add(t, p, "*", "R1 Completude", "vermelho", "trimestre ausente na base")
                continue
            # R1
            for c in OBRIGATORIOS:
                if r.get(c) is None:
                    log.add(t, p, c, "R1 Completude", "vermelho", "campo obrigatório ausente")
            # R2
            fco, capex, fcf = r.get("fluxo_caixa_operacional"), r.get("capex"), r.get("fcf")
            if None not in (fco, capex, fcf) and abs(fco + capex - fcf) > max(50, 0.01 * abs(fco)):
                log.add(t, p, "fcf", "R2 Coerência", "vermelho", f"FCF {fcf:,.0f} ≠ FCO + capex {fco + capex:,.0f}")
            if r.get("ebitda") is not None and r.get("receita") and r["ebitda"] > r["receita"]:
                log.add(t, p, "ebitda", "R2 Coerência", "vermelho", "EBITDA maior que a receita")
            # R3
            if r.get("ebitda") is not None and r.get("receita"):
                m = r["ebitda"] / r["receita"] * 100
                if not -20 <= m <= 80:
                    log.add(t, p, "ebitda", "R3 Plausibilidade", "vermelho", f"margem EBITDA {m:.1f}% fora da faixa −20% a 80%")
            if r.get("producao_kboed") is not None and r["producao_kboed"] <= 0:
                log.add(t, p, "producao_kboed", "R3 Plausibilidade", "vermelho", "produção não positiva")
            # R7 -- proveniência / quebra de fonte: a série da PoC é de fonte primária; trimestre que entrou
            # pelo agregador (update_fundamentals.py) fica com ressalva até ser substituído pelo release.
            if "primária" not in (r.get("fonte_dado") or ""):
                for c in ("receita", "lucro_liquido", "ebitda", "fluxo_caixa_operacional", "divida_liquida"):
                    log.add(t, p, c, "R7 Proveniência", "amarelo",
                            "valor provisório de agregador: substituir pelo release (poc/integra_fontes_primarias.py)")
            if r.get("fonte_dado"):
                txt = r["fonte_dado"]
                if "corrigid" in txt:
                    log.add(t, p, "divida_liquida", "R7 Proveniência", "amarelo",
                            "valor ajustado para a base padronizada (ver fonte_dado no JSON)")
            # R7 -- câmbio da Petrobras: dívida convertida pela PTAX de fechamento deve bater com a divulgada em US$
            cb = r.get("cambio")
            if cb and r.get("brl", {}).get("divida_liquida_brl"):
                usd = r["brl"]["divida_liquida_brl"] / cb["ptax_fechamento"]
                if abs(usd / cb["divida_usd_divulgada"] - 1) > 0.005:
                    log.add(t, p, "divida_liquida", "R7 Proveniência", "vermelho",
                            f"dívida pela PTAX de fechamento ({usd:,.0f}) difere da divulgada em US$ ({cb['divida_usd_divulgada']:,})")
            elif t == "PBR":
                log.add(t, p, "divida_liquida", "R7 Proveniência", "amarelo", "câmbio do trimestre não registrado")
            # R4/R5 -- desvio histórico vs. trimestre anterior
            if i == 0:
                continue
            prev = R.get(PERIODOS[i - 1])
            if prev is None:
                continue
            if p in BRENT and PERIODOS[i - 1] in BRENT:
                brent_var = BRENT[p] / BRENT[PERIODOS[i - 1]] - 1
            else:
                brent_var = 0.0
                if t == ORDEM_EMPRESAS[0]:
                    log.add("—", p, "brent", "R5 Contexto", "amarelo", "Brent do trimestre não informado em poc/contexto_mercado.json")
            for c, lim in LIMITES_VAR.items():
                a, b = prev.get(c), r.get(c)
                if a in (None, 0) or b is None:
                    continue
                if (a > 0) != (b > 0):
                    log.add(t, p, c, "R4 Desvio histórico", "amarelo",
                            f"troca de sinal {a:,.0f} → {b:,.0f}: verificar itens não recorrentes (impairment)")
                    continue
                var = b / a - 1
                if abs(var) > lim:
                    # R5 exige direção E magnitude compatíveis com o Brent: variação até ELASTICIDADE_MAX × a do Brent.
                    # (antes bastava a direção, o que "justificava" EBITDA +104% com Brent +25%)
                    explicado = (var * brent_var > 0 and abs(brent_var) >= 0.08
                                 and abs(var) <= ELASTICIDADE_MAX * abs(brent_var))
                    msg = f"variação {var:+.0%} t/t (limite ±{lim:.0%})"
                    if explicado:
                        msg += f" — compatível com o Brent ({brent_var:+.0%}) (R5)"
                    elif var * brent_var > 0 and abs(brent_var) >= 0.08:
                        razao = f"{abs(var / brent_var):.1f}".replace(".", ",")
                        msg += (f" — mesma direção do Brent ({brent_var:+.0%}), mas {razao}× a variação dele"
                                f" (acima de {ELASTICIDADE_MAX:.0f}×): ler o release")
                    log.add(t, p, c, "R4 Desvio histórico", "amarelo", msg, justificado=explicado)
            # Margem EBITDA: salto de mais de 15 p.p. sem contrapartida no Brent pede leitura
            if prev.get("ebitda") is not None and prev.get("receita") and r.get("ebitda") is not None and r.get("receita"):
                dm = (r["ebitda"] / r["receita"] - prev["ebitda"] / prev["receita"]) * 100
                if abs(dm) > 15:
                    explicado = dm * brent_var > 0 and abs(brent_var) >= 0.08
                    log.add(t, p, "ebitda", "R4 Desvio histórico", "amarelo",
                            f"margem EBITDA {dm:+.1f}".replace(".", ",") + " p.p. t/t" + (f" — Brent {brent_var:+.0%} (R5)" if explicado else
                            " sem contrapartida no Brent: checar itens não recorrentes"), justificado=explicado)
            # FCF: oscila com capital de giro e itens pontuais; variação material vs. o EBITDA do trimestre
            # anterior pede leitura e não é justificada pelo Brent.
            a, b = prev.get("fcf"), r.get("fcf")
            eb_q = abs(prev.get("ebitda") or 0)
            if a is not None and b is not None and eb_q and abs(b - a) > LIMITE_FCF * eb_q:
                log.add(t, p, "fcf", "R4 Desvio histórico", "amarelo",
                        f"FCF {a:,.0f} → {b:,.0f}: variação acima de {LIMITE_FCF:.0%} do EBITDA do trimestre anterior"
                        " (checar capital de giro e itens pontuais)")
            # Dívida líquida: materialidade medida contra o EBITDA anualizado.
            a, b = prev.get("divida_liquida"), r.get("divida_liquida")
            eb = abs(prev.get("ebitda") or 0) * 4 or 1
            if a is not None and b is not None:
                if (a > 0) != (b > 0) and min(abs(a), abs(b)) > 0.1 * eb:
                    log.add(t, p, "divida_liquida", "R4 Desvio histórico", "vermelho",
                            f"troca de sinal material {a:,.0f} → {b:,.0f}")
                elif abs(b - a) > 0.25 * eb:
                    log.add(t, p, "divida_liquida", "R4 Desvio histórico", "amarelo",
                            f"variação de {b - a:+,.0f} (> 25% do EBITDA anualizado)")
        # R6 -- revisão de dado já publicado (snapshot congelado do 1T26)
        if t in snap:
            s = snap[t]["q_recente"]
            atual = R.get("2026-Q1", {})
            for c in OBRIGATORIOS:
                if s.get(c) is not None and atual.get(c) is not None and s[c] != atual[c]:
                    log.add(t, "2026-Q1", c, "R6 Revisão", "amarelo",
                            f"valor revisado desde o snapshot publicado: {s[c]:,} → {atual[c]:,}", justificado=True)
        # R8 -- reconciliação entre fontes
        fy = empresas[t]["fy2025"]
        q4 = R.get("2025-Q4", {})
        if fy.get("divida_liquida") is not None and q4.get("divida_liquida"):
            a, b = fy["divida_liquida"], q4["divida_liquida"]
            if (a > 0) != (b > 0) or abs(a - b) > 0.05 * abs(b):
                log.add(t, "FY2025", "divida_liquida", "R8 Reconciliação", "vermelho",
                        f"FY2025 {a:,.0f} vs. 4T25 {b:,.0f} na mesma data-base")
        for c in ("receita", "ebitda"):
            soma = [R.get(p, {}).get(c) for p in PERIODOS[:4]]
            if fy.get(c) and None not in soma:
                dif = sum(soma) / fy[c] - 1
                if abs(dif) > 0.03:
                    log.add(t, "FY2025", c, "R8 Reconciliação", "amarelo",
                            f"soma dos trimestres de 2025 difere do FY2025 em {dif:+.1%} (definição do provedor anual)",
                            justificado=True)
        # R1/R7 -- efetivo
        ef = empresas[t].get("efetivo") or {}
        if not ef.get("2025-12-31"):
            log.add(t, "2025-Q4", "efetivo", "R1 Completude", "amarelo", "efetivo não informado")
        elif not ef.get("fonte_primaria"):
            log.add(t, "2025-Q4", "efetivo", "R7 Proveniência", "amarelo",
                    "efetivo de fonte secundária — confirmar no relatório anual/20-F")
    log.aplica_leituras(LEITURAS)
    return log


# --------------------------------------------------------------------------- #
# Indicadores
# --------------------------------------------------------------------------- #
def calcula(empresas, base, log):
    fato = []

    def add(t, p, cod, valor, status, obs, fonte):
        h = hashlib.sha1(f"{t}|{p}|{cod}|{valor}".encode()).hexdigest()[:10]
        fato.append(dict(empresa=t, periodo=p, rotulo=ROTULO[p], indicador=cod,
                         valor=None if valor is None else round(valor, IND[cod][4] if IND[cod][4] else 0),
                         unidade=IND[cod][2], status=status, obs=obs, fonte=fonte, hash=h))

    for t in ORDEM_EMPRESAS:
        R = base[t]
        ef = empresas[t].get("efetivo") or {}
        for i, p in enumerate(PERIODOS):
            r = R.get(p)
            if r is None:
                continue
            fonte = "F-REL-1T25" if p == "2025-Q1" else f"F-{t}"

            def st(cod, extra=(), t=t, p=p):
                pior = "verde"
                for c in INSUMOS[cod] + list(extra):
                    s = log.status_campo(t, p, c)
                    if SEV_ORD[s] > SEV_ORD[pior]:
                        pior = s
                return pior

            rec, eb, ll = r.get("receita"), r.get("ebitda"), r.get("lucro_liquido")
            add(t, p, "margem_ebitda", eb / rec * 100 if rec and eb is not None else None, st("margem_ebitda"), "", fonte)
            add(t, p, "margem_liquida", ll / rec * 100 if rec and ll is not None else None, st("margem_liquida"), "", fonte)
            add(t, p, "fcf", r["fcf"] / 1000 if r.get("fcf") is not None else None, st("fcf"), "", fonte)
            # ND / EBITDA: TTM quando a janela de 4 trimestres existe na base
            janela = PERIODOS[i - 3:i + 1] if i >= 3 else []
            obs = ""
            if janela and all(R.get(x, {}).get("ebitda") is not None for x in janela):
                ebitda_12m = sum(R[x]["ebitda"] for x in janela)
                status_nd = st("nd_ebitda")
                for x in janela:
                    s = log.status_campo(t, x, "ebitda")
                    if SEV_ORD[s] > SEV_ORD[status_nd]:
                        status_nd = s
                        obs = f"janela TTM inclui EBITDA com ressalva ({ROTULO[x]})"
            else:
                ebitda_12m = eb * 4 if eb is not None else None
                status_nd = "amarelo" if st("nd_ebitda") == "verde" else st("nd_ebitda")
                obs = "EBITDA do trimestre ×4 (janela TTM indisponível antes do 4T25)"
            nd = r.get("divida_liquida")
            add(t, p, "nd_ebitda", nd / ebitda_12m if nd is not None and ebitda_12m else None, status_nd, obs, fonte)
            prod = r.get("producao_kboed")
            add(t, p, "ebitda_boe", eb * 1000 / (prod * DIAS[p]) if eb is not None and prod else None,
                st("ebitda_boe"), "inclui downstream nas integradas", fonte)
            # Efetivo: ultimo valor anual divulgado ate o fim do trimestre
            anos = sorted(k for k in ef if k[:4].isdigit() and k[:4] + "-Q4" <= p)
            data_ref = anos[-1] if anos else None
            v_ef = ef.get(data_ref) if data_ref else None
            if data_ref and p == data_ref[:4] + "-Q4":
                s_ef = "verde" if ef.get("fonte_primaria") else "amarelo"
                o_ef = "" if ef.get("fonte_primaria") else "fonte secundária"
            else:
                s_ef = "amarelo"
                o_ef = (f"valor de {data_ref[8:]}/{data_ref[5:7]}/{data_ref[:4]} repetido (divulgação anual)" if data_ref
                        else "sem efetivo anual anterior ao trimestre")
            add(t, p, "efetivo", v_ef, s_ef if v_ef else "vermelho", o_ef, f"H-{t}")
            if janela and v_ef and all(R.get(x, {}).get("ebitda") is not None for x in janela):
                add(t, p, "ebitda_por_empregado", ebitda_12m * 1000 / v_ef,
                    "amarelo" if s_ef != "verde" else "verde", "EBITDA TTM ÷ efetivo", f"H-{t}")
    return fato


def dimensoes(empresas):
    dim_emp = [dict(empresa=t, nome=PERFIL[t][0], pais=PERFIL[t][1], padrao_contabil=PERFIL[t][2],
                    perfil=PERFIL[t][3], na_poc=t in POC_EMPRESAS, ordem=k + 1)
               for k, t in enumerate(ORDEM_EMPRESAS)]
    dim_per = [dict(periodo=p, rotulo=ROTULO[p], ordem=k + 1, data_fim=FIM[p], dias=DIAS[p], brent_medio=BRENT.get(p))
               for k, p in enumerate(PERIODOS)]
    dim_ind = [dict(indicador=c, nome=n, unidade=u, direcao=d, casas=cs, formula=f, grupo=g, ordem=k + 1)
               for k, (c, n, u, d, cs, f, g) in enumerate(INDICADORES)]
    fontes = json.loads((POC / "fontes.json").read_text(encoding="utf-8"))
    for t in ORDEM_EMPRESAS:
        ef = empresas[t].get("efetivo") or {}
        url = ef.get("fonte", "")
        host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", url).split("/")[0])
        # "fonte" descreve o documento (não repete a URL, que fica em url_primaria)
        fontes.append(dict(id=f"H-{t}", empresa=PERFIL[t][0], tipo="Total de efetivo (31/12)",
                           fonte=f"{host} · {ef.get('observacao', '')}".strip(" ·"), url_primaria=url,
                           alternativa_direta=ef.get("observacao", ""), coletado_em="2026-10-02",
                           frequencia="Anual", primaria=bool(ef.get("fonte_primaria"))))
    return dim_emp, dim_per, dim_ind, fontes


def escreve_csv(caminho, linhas):
    if not linhas:
        return
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default=str(JSON_DADOS), help="arquivo de dados a auditar (padrão: o do repositório)")
    ap.add_argument("--evidencia", help="só audita --json e grava o log de QA neste CSV (não gera painel)")
    ap.add_argument("--check", action="store_true", help="so roda o QA; sai com 1 se houver vermelho no recorte da PoC")
    args = ap.parse_args(argv)

    dados, empresas, base = carrega(args.json)
    log = aplica_regras(dados, empresas, base)
    if args.evidencia:
        escreve_csv(Path(args.evidencia), log.itens)
        verm = [x for x in log.itens if x["severidade"] == "vermelho"]
        print(f"QA de {args.json}: {len(log.itens)} alertas, {len(verm)} vermelhos")
        for x in verm:
            print(f"  {x['empresa']} {x['periodo']} {x['campo']}: {x['regra']} — {x['mensagem']}")
        return 0
    fato = calcula(empresas, base, log)
    dim_emp, dim_per, dim_ind, fontes = dimensoes(empresas)

    vermelhos_poc = [x for x in log.itens if x["severidade"] == "vermelho" and x["empresa"] in POC_EMPRESAS]
    if args.check:
        for x in vermelhos_poc:
            print(f"VERMELHO {x['empresa']} {x['periodo']} {x['campo']}: {x['mensagem']}")
        return 1 if vermelhos_poc else 0

    payload = dict(meta=dict(gerado_em=dados["referencia"].get("atualizado_em"), versao_dados=dados["referencia"].get("versao_dados"),
                             periodos=PERIODOS, poc=POC_EMPRESAS),
                   fato=fato, qa=log.itens, dim_empresa=dim_emp, dim_periodo=dim_per,
                   dim_indicador=dim_ind, fontes=fontes, leituras=LEITURAS,
                   ptax={p: v for p, v in PTAX.get("trimestres", {}).items() if p in PERIODOS},
                   evidencia=json.loads((POC / "evidencia_qa_v12.json").read_text(encoding="utf-8"))
                   if (POC / "evidencia_qa_v12.json").exists() else None)
    (POC / "poc_data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    escreve_csv(POC / "fato_indicador.csv", fato)
    escreve_csv(POC / "qa_log.csv", log.itens)
    escreve_csv(POC / "dim_empresa.csv", dim_emp)
    escreve_csv(POC / "dim_periodo.csv", dim_per)
    escreve_csv(POC / "dim_indicador.csv", dim_ind)
    escreve_csv(POC / "dim_fonte.csv", fontes)
    tpl = (POC / "painel_template.html").read_text(encoding="utf-8")
    html = tpl.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
    (POC / "painel_benchmarking_poc.html").write_text(html, encoding="utf-8")

    cont = {}
    for x in log.itens:
        cont[x["severidade"]] = cont.get(x["severidade"], 0) + 1
    print(f"OK: {len(fato)} registros; alertas {cont}; vermelhos no recorte PoC: {len(vermelhos_poc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
