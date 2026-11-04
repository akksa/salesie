import { useIsMutating, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { LIVE_POLL_MS, queryKeys } from "@/api/queryKeys";
import type { DealDetail, DealStage, PipelineOut } from "@/api/types";
import { findCard, moveCard } from "./movePipeline";

const MOVE_KEY = ["move-deal"] as const;

/** Board data. Polling stops while a drag or a move is in flight so it can't undo the optimistic state. */
export function usePipeline({ paused }: { paused: boolean }) {
  const moving = useIsMutating({ mutationKey: MOVE_KEY }) > 0;
  return useQuery({
    queryKey: queryKeys.pipeline,
    queryFn: () => api.get<PipelineOut>("/api/pipeline"),
    refetchInterval: paused || moving ? false : LIVE_POLL_MS,
  });
}

/** Chats waiting for the owner, for the nav badge. Shares the board's cache; slower poll, and none mid-move. */
export function usePipelineNeedsOwner() {
  const moving = useIsMutating({ mutationKey: MOVE_KEY }) > 0;
  return useQuery({
    queryKey: queryKeys.pipeline,
    queryFn: () => api.get<PipelineOut>("/api/pipeline"),
    select: (pipeline) => pipeline.needs_owner,
    refetchInterval: moving ? false : 15_000,
  });
}

export function useDeal(id: number | null) {
  return useQuery({
    queryKey: queryKeys.deal(id ?? 0),
    queryFn: () => api.get<DealDetail>(`/api/deals/${id}`),
    refetchInterval: LIVE_POLL_MS,
    enabled: id !== null && Number.isInteger(id) && id > 0,
  });
}

export interface MoveInput {
  dealId: number;
  /** Omit to change only the amount. */
  stage?: DealStage;
  /** Optional deal value to record with the move (e.g. a cash sale when marking won). */
  amountMinor?: number;
}

/** Move a deal to any stage. Optimistic on the board; rolled back (and the error surfaced) on failure. */
export function useMoveDeal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: MOVE_KEY,
    mutationFn: ({ dealId, stage, amountMinor }: MoveInput) =>
      api.patch<DealDetail>(`/api/deals/${dealId}`, {
        ...(stage !== undefined && { stage }),
        ...(amountMinor !== undefined && { amount_minor: amountMinor }),
      }),
    onMutate: async ({ dealId, stage, amountMinor }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.pipeline });
      const previous = queryClient.getQueryData<PipelineOut>(queryKeys.pipeline);
      const card = findCard(previous, dealId);
      if (previous && card) {
        queryClient.setQueryData(
          queryKeys.pipeline,
          moveCard(previous, dealId, stage ?? card.stage, amountMinor),
        );
      }
      return { previous };
    },
    onError: (_error, _input, context) => {
      if (context?.previous) queryClient.setQueryData(queryKeys.pipeline, context.previous);
    },
    onSuccess: (deal) => {
      queryClient.setQueryData(queryKeys.deal(deal.id), deal);
    },
    onSettled: () => {
      for (const key of [queryKeys.pipeline, queryKeys.deals, queryKeys.contacts]) {
        void queryClient.invalidateQueries({ queryKey: key });
      }
      void queryClient.invalidateQueries({ queryKey: ["insights"] });
    },
  });
}
