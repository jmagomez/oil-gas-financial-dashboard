import { Moon, Sun } from 'lucide-react';
import { useTheme } from '@/hooks/use-theme';

export function ThemeToggle() {
  const { tema, alterna } = useTheme();
  const proximo = tema === 'escuro' ? 'claro' : 'escuro';

  return (
    <button
      type="button"
      onClick={alterna}
      // aria-label diz o que o botao FAZ, nao o estado atual: leitor de tela
      // anuncia a acao, e "tema escuro" sozinho nao diz se liga ou desliga.
      aria-label={`Mudar para o tema ${proximo}`}
      className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm text-muted transition-colors hover:text-fg"
    >
      {tema === 'escuro' ? (
        <Sun aria-hidden className="h-4 w-4" />
      ) : (
        <Moon aria-hidden className="h-4 w-4" />
      )}
      <span className="hidden sm:inline">Tema {proximo}</span>
    </button>
  );
}
