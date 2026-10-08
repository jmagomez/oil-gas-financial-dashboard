"""Demonstração ao vivo: o erro real da dívida líquida da Equinor no 1T26 e o que os controles fazem.

Uso (dentro da pasta repositorio):  python poc/demo_erro_equinor.py
Roda as regras de qualidade em três versões do mesmo dado, só em memória (nada é gravado):
  v1.2  -4.209  (sinal invertido, vindo do agregador)
  v1.3  +4.209  (sinal corrigido, módulo ainda errado)
  v1.4  11.761  (6-K da Equinor de 06/05/2026: dívida bruta 31.857 - caixa 5.884 - aplicações 14.212)
"""
import copy
import importlib.util
import pathlib
import statistics

RAIZ = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_poc", RAIZ / "poc" / "build_poc.py")
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)

P = "2026-Q1"
CENARIOS = [("v1.2 (agregador)", -4209), ("v1.3 (só o sinal corrigido)", 4209), ("v1.4 (6-K da Equinor)", 11761)]

dados, empresas, base0 = bp.carrega()
print(f"Equinor, dívida líquida em 31/12/2025 (4T25): {base0['EQNR']['2025-Q4']['divida_liquida']:,} US$ mi; "
      f"EBITDA do 4T25: {base0['EQNR']['2025-Q4']['ebitda']:,}\n")

for nome, nd in CENARIOS:
    base = copy.deepcopy(base0)
    base["EQNR"][P]["divida_liquida"] = nd
    log = bp.aplica_regras(dados, empresas, base)
    fato = bp.calcula(empresas, base, log)
    alertas = [a for a in log.itens if a["empresa"] == "EQNR" and a["periodo"] == P and a["campo"] == "divida_liquida"]
    v = {f["empresa"]: f for f in fato if f["periodo"] == P and f["indicador"] == "nd_ebitda"}
    pares = [v[e]["valor"] for e in ("XOM", "SHEL", "EQNR") if e in v and v[e]["status"] != "vermelho" and v[e]["valor"] is not None]
    print(f"== {nome}: dívida líquida da Equinor = {nd:,}")
    print("   Controles:", "; ".join(f"{a['regra']} [{a['severidade']}] {a['mensagem']}" for a in alertas) or "NENHUM alerta")
    eq = v["EQNR"]
    print(f"   DL/EBITDA da Equinor: {eq['valor']:.2f}x  selo: {eq['status']}"
          + ("  -> fora das medianas e rankings" if eq["status"] == "vermelho" else ""))
    x = {f["empresa"]: f for f in fato if f["periodo"] == P and f["indicador"] == "nd_ex_arrend_ebitda"}["EQNR"]
    print(f"   DL sem arrendamentos/EBITDA da Equinor: {x['valor']:.2f}x")
    print(f"   Mediana dos pares (PoC): {statistics.median(pares):.2f}x  | Petrobras: {v['PBR']['valor']:.2f}x\n")
