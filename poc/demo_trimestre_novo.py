"""Demonstração ao vivo: um 3T26 entra na base sem mudar código e a janela desloca.

Uso (dentro da pasta repositorio):  python poc/demo_trimestre_novo.py
Nada é gravado em disco: o trimestre novo é uma cópia do 2T26, só em memória.
"""
import copy
import importlib.util
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_poc", RAIZ / "poc" / "build_poc.py")
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)

dados, empresas, base = bp.carrega()
antes = bp.define_periodos(base)
print("Janela atual:      ", " · ".join(antes))

base = copy.deepcopy(base)
for t in base:  # simula o release do 3T26 de cada empresa (cópia do 2T26)
    base[t]["2026-Q3"] = dict(base[t]["2026-Q2"])

depois = bp.define_periodos(base)
log = bp.aplica_regras(dados, empresas, base)
fato = bp.calcula(empresas, base, log)
novos = [f for f in fato if f["periodo"] == "2026-Q3"]
print("Janela com o 3T26: ", " · ".join(depois))
print(f"Registros do 3T26 calculados: {len(novos)} ({len({f['empresa'] for f in novos})} empresas)")
print(f"Saiu da exibição: {sorted(set(antes) - set(depois))} (continua na base primária poc/coleta/ e no Git)")
print("Nenhuma linha de código foi alterada.")
