import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { promptsApi } from "@/lib/api/endpoints";
import type {
  ActivatePromptRequest,
  CreatePromptRequest,
} from "@/lib/api/types";

export const PROMPTS_KEY = ["prompts"] as const;
export const CHANGELOG_KEY = ["prompts", "changelog"] as const;

export function usePrompts() {
  return useQuery({
    queryKey: PROMPTS_KEY,
    queryFn: promptsApi.list,
    staleTime: 30_000,
  });
}

export function usePromptsChangelog(limit = 50) {
  return useQuery({
    queryKey: [...CHANGELOG_KEY, limit],
    queryFn: () => promptsApi.changelog(limit),
    staleTime: 30_000,
  });
}

export function useCreatePrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: CreatePromptRequest) => promptsApi.create(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: PROMPTS_KEY }),
  });
}

export function useActivatePrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: ActivatePromptRequest) => promptsApi.activate(req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PROMPTS_KEY });
      qc.invalidateQueries({ queryKey: CHANGELOG_KEY });
    },
  });
}
