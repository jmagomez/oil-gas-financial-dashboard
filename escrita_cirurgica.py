#!/usr/bin/env python3
"""Primitivas compartilhadas de escrita cirúrgica em indicadores_oleo_gas.json.

`update_market_data.py` e `update_fundamentals.py` atualizam regimes de dado
diferentes (mercado muda todo pregão; fundamentos mudam a cada balanço), mas
os dois escrevem no MESMO arquivo curado à mão e pelo MESMO motivo: o arquivo
vivo usa objetos compactos de uma linha com zero à direita preservado, e
reserializar com json.dump() trocaria centenas de linhas de formatação a cada
execução — o diff diário deixaria de caber em "~8 linhas por empresa" e o
histórico do arquivo deixaria de ser legível.

As duas rotinas reimplementavam a mesma lógica (achar cada ticker no texto,
serializar um dict em uma linha respeitando uma ordem canônica, sincronizar o
campo "atualizado_em") com o mesmo formato de bug possível. Este módulo é o
lugar único para essa lógica; cada rotina mantém só o que é específico do seu
regime (quais blocos substituir, em que ordem).

Nada aqui fala com a rede nem conhece o schema de "mercado" ou "q_recente" —
só o formato de texto do arquivo.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date
from typing import Any

RE_TICKER = re.compile(r'"ticker":\s*"([A-Z.]+)"')
RE_INICIO_EMPRESAS = re.compile(r'"empresas":\s*\[')
RE_ATUALIZADO_EM = re.compile(r'("atualizado_em":\s*")\d{4}-\d{2}-\d{2}(")')


def posicoes_dos_tickers(bruto: str) -> list[tuple[str, int]]:
    """Posição (fim do casamento) de cada "ticker" DENTRO de "empresas", em ordem.

    Duas salvaguardas, e as duas existem pelo mesmo motivo: o resultado desta
    função é o pareamento ticker→bloco que as duas rotinas de escrita usam para
    decidir ONDE gravar. Se a lista sair deslocada, cada empresa recebe o bloco
    da seguinte — e isso não quebra nada visível: o arquivo continua JSON
    válido, nenhum campo some, e só os números ficam trocados entre companhias.

    1. A busca começa no início de `"empresas"`, não do arquivo. Qualquer chave
       `"ticker"` em `referencia` (um registro de exceções, um mapa de ADS, uma
       nota estruturada) entraria na lista antes das empresas e deslocaria tudo.
    2. A sequência encontrada no texto é conferida contra a estrutura do JSON.
       Qualquer `"ticker"` extra DENTRO de uma empresa (em `proveniencia`, por
       exemplo) desloca do mesmo jeito, e o recorte sozinho não pegaria.

    Levanta ValueError nos dois casos — reescrever com pareamento duvidoso é
    pior do que não reescrever.
    """
    inicio = RE_INICIO_EMPRESAS.search(bruto)
    if inicio is None:
        raise ValueError('chave "empresas" nao encontrada no JSON; formato inesperado')

    posicoes = [(m.group(1), m.end()) for m in RE_TICKER.finditer(bruto, inicio.end())]
    if not posicoes:
        raise ValueError("nenhum ticker encontrado no JSON; formato inesperado")

    esperados = [e["ticker"] for e in json.loads(bruto)["empresas"]]
    if [t for t, _ in posicoes] != esperados:
        raise ValueError(
            f'sequencia de "ticker" no texto {[t for t, _ in posicoes]} nao bate com as '
            f"empresas do JSON {esperados}: o pareamento ticker->bloco ficaria deslocado "
            "e trocaria dados entre empresas"
        )
    return posicoes


def serializa_bloco_canonico(
    bloco: dict[str, Any],
    ordem: list[str],
    formata: Callable[[str, Any], str] | None = None,
) -> str:
    """Um dict em uma linha, na ordem canônica do arquivo.

    Chaves fora de `ordem` (extras que uma versão futura do schema tenha
    acrescentado) são preservadas ao final, na ordem em que aparecem no dict
    — nenhum dado é descartado por não estar na lista canônica.

    `formata(chave, valor) -> str` escolhe a representação textual de cada
    valor CANÔNICO; o padrão é `json.dumps`. Passe uma função própria quando
    o arquivo exigir uma forma que `json.dumps` não produz (ver
    `update_market_data._formata_numero`, que preserva o zero à direita em
    "6.00"). Chaves fora de `ordem` são sempre serializadas com `json.dumps`
    puro — são extras de schema futuro, de tipo não previsto, e não o dado
    numérico que `formata` foi desenhada para um campo específico.
    """
    f = formata or (lambda _chave, v: json.dumps(v, ensure_ascii=False))
    partes = [f'"{c}": {f(c, bloco[c])}' for c in ordem if c in bloco]
    partes += [
        f'"{c}": {json.dumps(v, ensure_ascii=False)}' for c, v in bloco.items() if c not in ordem
    ]
    return "{" + ", ".join(partes) + "}"


def atualiza_campo_data(bruto: str, hoje: date) -> str:
    """Sincroniza `"atualizado_em": "AAAA-MM-DD"` com a data de hoje.

    Mesmo campo, mesmo formato, nas duas rotinas — cada uma ainda cuida da
    sua própria nota textual adicional (o rodapé do dashboard, o cabeçalho do
    trimestre), que não é compartilhada entre os dois regimes.
    """
    return RE_ATUALIZADO_EM.sub(rf"\g<1>{hoje.isoformat()}\g<2>", bruto)
