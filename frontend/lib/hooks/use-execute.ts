import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { agentApi } from "@/lib/api/endpoints";
import type { AgentResponse, UserQuery } from "@/lib/api/types";

export const EXECUTE_KEY = ["agent", "execute"] as const;

export function useExecuteAgent() {
  const queryClient = useQueryClient();

  return useMutation<AgentResponse, Error, UserQuery>({
    mutationFn: agentApi.execute,
    onSuccess: () => {
      // Invalidate metrics so the dashboard reflects the new call
      queryClient.invalidateQueries({ queryKey: ["metrics"] });
    },
  });
}
