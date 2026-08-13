# Snapshot congelado dos dados primarios

Os testes de **logica** leem de `indicadores_snapshot.json`, nao de
`indicadores_oleo_gas.json`.

O arquivo vivo muda a cada balanco. Se os testes assertarem sobre ele, a
propria atualizacao dos dados quebra a suite -- e a trava "roda os testes
antes de commitar" passa a impedir para sempre o commit que deveria
proteger. Foi exatamente o que aconteceu na primeira tentativa de promover
o Q2 2026: 12 testes falharam e o commit foi bloqueado.

O snapshot e uma copia byte a byte do arquivo vivo em Q1 2026.

## O que NAO fica congelado

O contrato de **formato** do arquivo vivo continua sendo testado contra o
arquivo real, em
`test_update_market.test_formato_do_arquivo_vivo_suporta_escrita_cirurgica`.
Esse teste nao afirma nada sobre valores, so sobre o formato de que a
escrita cirurgica depende -- e foi ele que pegou uma versao de
`update_fundamentals.py` que reserializava o JSON e trocava ~500 linhas de
formatacao. Apontar tudo para o snapshot teria removido essa rede.

## Quando atualizar o snapshot

So quando o **schema** mudar (campo novo, campo removido, estrutura
diferente) -- nao quando os numeros mudarem. Se um teste de logica passou a
falhar porque os dados vivos mudaram, o teste e que esta acoplado demais.
