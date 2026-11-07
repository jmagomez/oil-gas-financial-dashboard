import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: 'hsl(var(--bg) / <alpha-value>)',
        surface: 'hsl(var(--surface) / <alpha-value>)',
        border: 'hsl(var(--border) / <alpha-value>)',
        fg: 'hsl(var(--fg) / <alpha-value>)',
        muted: 'hsl(var(--muted) / <alpha-value>)',
        accent: 'hsl(var(--accent) / <alpha-value>)',
        up: 'hsl(var(--up) / <alpha-value>)',
        down: 'hsl(var(--down) / <alpha-value>)',
        warn: 'hsl(var(--warn) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Inter var', 'Inter', 'system-ui', 'sans-serif'],
        // Tabular para numero: sem isso a coluna "danca" quando o valor muda,
        // porque os digitos tem larguras diferentes.
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      transitionDuration: { theme: '180ms' },
    },
  },
  plugins: [],
} satisfies Config;
