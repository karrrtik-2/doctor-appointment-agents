import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { circuitBreakerApi } from "@/lib/api/endpoints";

export const CB_KEY = ["circuit-breakers"] as const;

export function useCircuitBreakers() {
  return useQuery({
    queryKey: CB_KEY,
    queryFn: circuitBreakerApi.status,
    refetchInterval: 15_000,
    staleTime: 10_000,
  });
}

export function useResetCircuitBreaker() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => circuitBreakerApi.reset(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: CB_KEY }),
  });
}
