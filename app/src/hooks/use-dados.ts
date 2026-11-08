import { useQuery } from '@tanstack/react-query';
import { carregaDados } from '@/services/dashboard-data-api';

/**
 * O payload enriquecido tem ~45 KB e muda uma vez por dia util (rotina de
 * mercado) ou a cada balanco. Cache generoso: nada aqui e intradiario.
 */
export function useDados() {
  return useQuery({
    queryKey: ['dashboard-data'],
    queryFn: carregaDados,
    staleTime: 30 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  });
}
