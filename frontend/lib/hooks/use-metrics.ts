import { useQuery } from "@tanstack/react-query";
import { metricsApi } from "@/lib/api/endpoints";

export const METRICS_KEY = ["metrics"] as const;
export const METRICS_HISTORY_KEY = ["metrics", "history"] as const;

export function useMetrics(options?: { refetchInterval?: number }) {
  return useQuery({
    queryKey: METRICS_KEY,
    queryFn: metricsApi.dashboard,
    refetchInterval: options?.refetchInterval ?? 30_000,
    staleTime: 10_000,
    retry: 1,
  });
}

export function useMetricsHistory(limit = 100) {
  return useQuery({
    queryKey: [...METRICS_HISTORY_KEY, limit],
    queryFn: () => metricsApi.history(limit),
    staleTime: 10_000,
    retry: 1,
  });
}
