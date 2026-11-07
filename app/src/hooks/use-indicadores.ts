import { useQuery } from '@tanstack/react-query';
import { carregaIndicadores } from '@/services/indicadores-api';

/**
 * O payload tem ~21 KB e muda uma vez por dia util (rotina de mercado) ou a
 * cada balanco (fundamentos). Cache generoso: nao ha nada intradiario aqui.
 */
export function useIndicadores() {
  return useQuery({
    queryKey: ['indicadores'],
    queryFn: carregaIndicadores,
    staleTime: 30 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  });
}
