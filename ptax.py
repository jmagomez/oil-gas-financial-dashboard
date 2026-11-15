#!/usr/bin/env python3
"""PTAX de venda do Banco Central, por trimestre.

Existe por causa de uma empresa: a Petrobras publica em reais e este projeto
declara "USD (milhoes)". A conversao e curadoria com regra, e a regra e a que a
propria companhia usa nos seus releases:

    FLUXO   (receita, lucro, EBITDA, FCO, capex)  ->  PTAX MEDIA do trimestre
    ESTOQUE (divida, caixa, patrimonio, ativos)   ->  PTAX de FECHAMENTO do
                                                      ultimo dia util

Trocar uma pela outra nao e detalhe. No 2T26 a media foi 5,0494 e o fechamento
5,1766: converter a receita pelo fechamento a encolheria 2,5%, e converter a
divida pela media a inflaria na mesma proporcao -- os dois erros com cara de
numero certo.

A regra foi conferida contra o que a Petrobras divulga em dolar: a divida
liquida de R$ 312.602 milhoes do 2T26, pelo fechamento, da US$ 60.388 milhoes
-- exatamente o numero do release.

O arquivo `ptax/raw.txt` (dd/mm/aaaa;taxa, uma cotacao por dia util) fica no
repositorio de proposito: quem audita um numero convertido precisa poder refazer
a media sem depender de uma API estar no ar.

Uso:
    python3 ptax.py                # mostra media e fechamento por trimestre
    python3 ptax.py --atualizar    # busca no Banco Central os dias que faltam
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent
ARQUIVO = RAIZ / "ptax" / "raw.txt"

# API de dados abertos do Banco Central (Olinda). `CotacaoDolarPeriodo` devolve
# o boletim de FECHAMENTO de cada dia util -- uma linha por dia.
URL = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoDolarPeriodo(dataInicial=@i,dataFinalCotacao=@f)"
    "?@i='{inicio}'&@f='{fim}'&$format=json&$select=cotacaoVenda,dataHoraCotacao"
)

# Um trimestre tem entre 59 e 66 dias uteis no Brasil. Abaixo de 55 a serie
# esta incompleta, e a "media do trimestre" seria a media de um pedaco dele.
MIN_DIAS_UTEIS = 55

# O ultimo dia util pode cair ate tres dias antes do fim do trimestre (fim de
# semana prolongado por feriado). Mais longe que isso, o "fechamento" lido nao
# e o fechamento.
FOLGA_FECHAMENTO_DIAS = 4

# Faixa de plausibilidade de uma cotacao diaria, em R$/US$. Pega virgula
# decimal perdida (51766) e resposta de outra moeda.
FAIXA = (2.0, 12.0)


class PtaxIncompleta(ValueError):
    """A serie nao cobre o trimestre pedido; converter com ela seria inventar."""


def _trimestre(d: date) -> str:
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def fim_do_trimestre(periodo: str) -> date:
    ano, q = int(periodo[:4]), int(periodo[-1])
    mes = 3 * q
    proximo = date(ano + (mes == 12), mes % 12 + 1, 1)
    return proximo - timedelta(days=1)


def le(caminho: Path = ARQUIVO) -> dict[date, float]:
    """Le o arquivo de cotacoes. Linha malformada e erro, nao aviso."""
    cotacoes: dict[date, float] = {}
    for n, linha in enumerate(caminho.read_text(encoding="utf-8").split(), start=1):
        try:
            dia, taxa = linha.split(";")
            d = datetime.strptime(dia, "%d/%m/%Y").date()
            v = float(taxa.replace(",", "."))
        except ValueError as exc:
            raise ValueError(f"{caminho.name}, linha {n}: {linha!r} ilegivel") from exc
        if not FAIXA[0] <= v <= FAIXA[1]:
            raise ValueError(f"{caminho.name}, linha {n}: cotacao {v} fora da faixa {FAIXA}")
        cotacoes[d] = v
    return cotacoes


def por_trimestre(cotacoes: dict[date, float]) -> dict[str, dict[str, Any]]:
    """Media aritmetica dos dias uteis e taxa do ultimo dia util, por trimestre."""
    grupos: dict[str, list[tuple[date, float]]] = {}
    for d, v in cotacoes.items():
        grupos.setdefault(_trimestre(d), []).append((d, v))
    saida = {}
    for periodo, dias in sorted(grupos.items()):
        dias.sort()
        saida[periodo] = {
            "media": round(sum(v for _, v in dias) / len(dias), 4),
            "fechamento": dias[-1][1],
            "data_fechamento": dias[-1][0].isoformat(),
            "dias_uteis": len(dias),
        }
    return saida


def taxas(periodo: str, cotacoes: dict[date, float] | None = None) -> dict[str, Any]:
    """Media e fechamento de UM trimestre, ou PtaxIncompleta.

    A recusa e o ponto. Uma media calculada com metade do trimestre e um
    "fechamento" de tres semanas antes do fim produzem numeros perfeitamente
    plausiveis -- e errados. Sem a serie completa, o trimestre nao e convertido,
    e portanto nao e promovido.
    """
    cotacoes = le() if cotacoes is None else cotacoes
    t = por_trimestre(cotacoes).get(periodo)
    if t is None:
        raise PtaxIncompleta(f"sem nenhuma cotacao PTAX para {periodo}")
    if t["dias_uteis"] < MIN_DIAS_UTEIS:
        raise PtaxIncompleta(
            f"PTAX de {periodo} com {t['dias_uteis']} dias uteis (minimo {MIN_DIAS_UTEIS})"
        )
    fim = fim_do_trimestre(periodo)
    ultimo = date.fromisoformat(t["data_fechamento"])
    if (fim - ultimo).days > FOLGA_FECHAMENTO_DIAS:
        raise PtaxIncompleta(
            f"ultima PTAX de {periodo} e de {ultimo.isoformat()}, "
            f"a {(fim - ultimo).days} dias do fim do trimestre"
        )
    return t


def interpreta_resposta(corpo: str) -> dict[date, float]:
    """Traduz o JSON da API do Banco Central em {dia: cotacao de venda}."""
    cotacoes: dict[date, float] = {}
    for item in json.loads(corpo).get("value", []):
        d = datetime.fromisoformat(item["dataHoraCotacao"][:10]).date()
        v = float(item["cotacaoVenda"])
        if not FAIXA[0] <= v <= FAIXA[1]:
            raise ValueError(f"PTAX de {d.isoformat()} fora da faixa {FAIXA}: {v}")
        cotacoes[d] = v
    return cotacoes


def baixa(inicio: date, fim: date) -> dict[date, float]:  # pragma: no cover - rede
    url = URL.format(inicio=inicio.strftime("%m-%d-%Y"), fim=fim.strftime("%m-%d-%Y"))
    pedido = urllib.request.Request(url, headers={"User-Agent": "oil-gas-financial-dashboard"})
    with urllib.request.urlopen(pedido, timeout=60) as resposta:
        return interpreta_resposta(resposta.read().decode("utf-8"))


def acrescenta(novas: dict[date, float], caminho: Path = ARQUIVO) -> int:
    """Acrescenta ao arquivo so os dias que ele ainda nao tem. Devolve quantos.

    Dia ja gravado NAO e sobrescrito: a PTAX de um dia fechado nao muda, e se a
    API devolver outro valor para ele o certo e parar e olhar, nao corrigir em
    silencio um numero que ja converteu balanco publicado.
    """
    atuais = le(caminho)
    for d, v in novas.items():
        if d in atuais and abs(atuais[d] - v) > 1e-9:
            raise ValueError(
                f"PTAX de {d.isoformat()} diverge: arquivo {atuais[d]}, fonte {v}. "
                "Um dia fechado nao deveria mudar."
            )
    faltantes = sorted((d, v) for d, v in novas.items() if d not in atuais)
    if not faltantes:
        return 0
    texto = caminho.read_text(encoding="utf-8")
    if texto and not texto.endswith("\n"):
        texto += "\n"
    texto += "".join(f"{d:%d/%m/%Y};{v:.4f}".replace(".", ",") + "\n" for d, v in faltantes)
    caminho.write_text(texto, encoding="utf-8")
    return len(faltantes)


def atualiza(hoje: date | None = None, caminho: Path = ARQUIVO) -> int:  # pragma: no cover - rede
    """Busca do dia seguinte ao ultimo gravado ate ontem (o boletim de hoje pode nao ter fechado)."""
    hoje = hoje or date.today()
    ultimo = max(le(caminho))
    inicio, fim = ultimo + timedelta(days=1), hoje - timedelta(days=1)
    if inicio > fim:
        return 0
    return acrescenta(baixa(inicio, fim), caminho)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--atualizar", action="store_true", help="busca no Banco Central os dias que faltam")
    args = parser.parse_args(argv)
    if args.atualizar:
        print(f"PTAX: {atualiza()} dia(s) acrescentado(s) a {ARQUIVO.relative_to(RAIZ)}")
    for periodo, t in por_trimestre(le()).items():
        print(f"  {periodo}  media {t['media']:.4f}  fechamento {t['fechamento']:.4f} "
              f"({t['data_fechamento']})  {t['dias_uteis']} dias uteis")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
