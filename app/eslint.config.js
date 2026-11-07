import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import query from '@tanstack/eslint-plugin-query';
import prettier from 'eslint-config-prettier';
import globals from 'globals';

export default tseslint.config(
  { ignores: ['dist', 'coverage', 'node_modules'] },

  js.configs.recommended,

  // As regras com tipo valem SO para .ts/.tsx: aplicadas aos .js de config,
  // elas pedem um tsconfig que nao os inclui e o lint falha no proprio
  // arquivo de lint.
  {
    files: ['**/*.{ts,tsx}'],
    extends: [...tseslint.configs.recommendedTypeChecked],
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
      globals: { ...globals.browser },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      'jsx-a11y': jsxA11y,
      '@tanstack/query': query,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.flatConfigs.recommended.rules,
      ...query.configs['flat/recommended'].rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],

      // Regra de ARQUITETURA, nao de estilo: componente nao chama fetch nem
      // schema direto. Tudo passa por services/ -- e o que torna "o pipeline
      // mudou o payload" um erro localizado em vez de um sintoma distante.
      // `allowTypeImports` porque types/ importa os schemas SO como tipo,
      // para o guard de divergencia em tempo de compilacao.
      '@typescript-eslint/no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@/services/schemas/*'],
              message: 'use services/indicadores-api; o schema é a fronteira, não a UI',
              allowTypeImports: true,
            },
          ],
        },
      ],
    },
  },

  // Testes e scripts podem falar com o schema direto: e exatamente o que eles
  // verificam.
  {
    files: ['tests/**/*.{ts,tsx}', 'scripts/**/*.ts'],
    rules: { '@typescript-eslint/no-restricted-imports': 'off' },
  },

  { files: ['**/*.js'], extends: [tseslint.configs.disableTypeChecked] },

  prettier,
);
