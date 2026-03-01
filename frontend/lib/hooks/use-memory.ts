import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memoryApi } from "@/lib/api/endpoints";

export function usePatientMemory(userId: string, tenantId: string) {
  return useQuery({
    queryKey: ["memory", userId, tenantId],
    queryFn: () => memoryApi.getContext(userId, tenantId),
    enabled: userId.length >= 7,
    staleTime: 60_000,
    retry: 1,
  });
}

export function useDeletePatientMemory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      userId,
      tenantId,
    }: {
      userId: string;
      tenantId: string;
    }) => memoryApi.deleteAll(userId, tenantId),
    onSuccess: (_data, { userId, tenantId }) => {
      queryClient.invalidateQueries({
        queryKey: ["memory", userId, tenantId],
      });
    },
  });
}
