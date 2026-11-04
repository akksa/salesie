import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import type { InsightsOut } from "@/api/types";

export const PERIODS = [7, 30, 90] as const;
export type Period = (typeof PERIODS)[number];

export function useInsights(days: Period) {
  return useQuery({
    queryKey: queryKeys.insights(days),
    queryFn: () => api.get<InsightsOut>(`/api/insights?days=${days}`),
    refetchInterval: 30_000,
    // Keep the old numbers on screen while a new period loads, instead of flashing skeletons.
    placeholderData: keepPreviousData,
  });
}
