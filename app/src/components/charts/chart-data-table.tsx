import { useId, useState } from 'react';
import { Table2 } from 'lucide-react';

export interface ColunaTabela {
  chave: string;
  rotulo: string;
}

interface Props {
  titulo: string;
  colunas: readonly ColunaTabela[];
  linhas: ReadonlyArray<Record<string, string>>;
}

/**
 * Tabela equivalente ao grafico.
 *
 * Mesmo em SVG, uma serie com dezenas de pontos nao e navegavel por leitor de
 * tela. A tabela e a forma acessivel do MESMO dado -- e, na pratica, tambem e
 * como um analista confere um valor exato sem passar o mouse ponto a ponto.
 * Por isso ela e visivel sob demanda, e nao escondida em `sr-only`: recurso
 * util para todos desaparece quando so o leitor de tela o alcanca.
 */
export function ChartDataTable({ titulo, colunas, linhas }: Props) {
  const [aberta, setAberta] = useState(false);
  const id = useId();

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setAberta((v) => !v)}
        aria-expanded={aberta}
        aria-controls={id}
        className="inline-flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-xs text-muted transition-colors hover:text-fg"
      >
        <Table2 aria-hidden className="h-3.5 w-3.5" />
        {aberta ? 'Ocultar' : 'Ver'} dados em tabela
      </button>

      {aberta && (
        <div id={id} className="mt-2 max-h-72 overflow-auto rounded-lg border border-border">
          <table className="w-full text-xs">
            <caption className="sr-only">{titulo}</caption>
            <thead className="sticky top-0 bg-surface text-muted">
              <tr>
                {colunas.map((c) => (
                  <th key={c.chave} scope="col" className="px-2 py-1.5 text-right font-medium">
                    {c.rotulo}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {linhas.map((l, i) => (
                <tr key={i} className="border-t border-border">
                  {colunas.map((c, j) => {
                    const valor = l[c.chave] ?? '—';
                    // A primeira coluna e o rotulo da linha, nao um dado:
                    // marca-la como `th scope="row"` e o que permite ao leitor
                    // de tela anunciar "Receita, 323.910" em vez de so o numero.
                    return j === 0 ? (
                      <th key={c.chave} scope="row" className="px-2 py-1.5 text-left font-medium">
                        {valor}
                      </th>
                    ) : (
                      <td key={c.chave} className="px-2 py-1.5 text-right tabular-nums">
                        {valor}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
