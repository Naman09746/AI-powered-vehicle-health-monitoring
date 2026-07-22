"use client";

import { useQuery } from "@tanstack/react-query";
import { recommendationApi } from "@/lib/api";

export function useRecommendations(vehicleId: number | null) {
  return useQuery({
    queryKey: ["recommendations", vehicleId],
    queryFn: () => recommendationApi.list(vehicleId!).then((r) => r.data),
    enabled: !!vehicleId,
    refetchInterval: 15_000,
  });
}
