import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { costsApi } from "@/lib/api/endpoints";

export const COSTS_KEY = ["costs"] as const;

export function useCosts(since?: number) {
  return useQuery({
    queryKey: [...COSTS_KEY, since],
    queryFn: () => costsApi.summary(since),
    staleTime: 30_000,
  });
}

export function useTenantCosts(tenantId: string, since?: number) {
  return useQuery({
    queryKey: [...COSTS_KEY, "tenant", tenantId, since],
    queryFn: () => costsApi.forTenant(tenantId, since),
    enabled: !!tenantId,
    staleTime: 30_000,
  });
}
