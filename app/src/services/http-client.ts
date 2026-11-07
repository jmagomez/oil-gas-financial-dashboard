/** Erro de dados com o arquivo no nome: o log diz O QUE falhou, nao so que falhou. */
export class ErroDeDados extends Error {
  constructor(
    mensagem: string,
    readonly arquivo: string,
    readonly causa?: unknown,
  ) {
    super(mensagem);
    this.name = 'ErroDeDados';
  }
}

/**
 * Caminho RELATIVO de proposito: em producao o app vive em
 * /oil-gas-financial-dashboard/app/ e o dado em ./data/ ao lado dele. Caminho
 * absoluto quebraria ao publicar em subcaminho.
 */
export async function buscaJson(arquivo: string): Promise<unknown> {
  const url = `./data/${arquivo}`;
  let resposta: Response;
  try {
    resposta = await fetch(url, { headers: { Accept: 'application/json' } });
  } catch (causa) {
    throw new ErroDeDados(`não foi possível buscar ${arquivo}`, arquivo, causa);
  }
  if (!resposta.ok) {
    throw new ErroDeDados(`${arquivo}: HTTP ${resposta.status} ${resposta.statusText}`, arquivo);
  }
  try {
    return await resposta.json();
  } catch (causa) {
    throw new ErroDeDados(`${arquivo}: resposta não é JSON válido`, arquivo, causa);
  }
}
