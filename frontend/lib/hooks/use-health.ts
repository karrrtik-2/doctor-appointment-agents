import { useQuery } from "@tanstack/react-query";
import { healthApi } from "@/lib/api/endpoints";

export const HEALTH_KEY = ["health"] as const;

export function useHealth(options?: { refetchInterval?: number }) {
  return useQuery({
    queryKey: HEALTH_KEY,
    queryFn: healthApi.check,
    refetchInterval: options?.refetchInterval ?? 30_000,
    staleTime: 15_000,
    retry: 2,
  });
}
