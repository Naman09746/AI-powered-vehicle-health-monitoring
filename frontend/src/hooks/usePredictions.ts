"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { predictionApi } from "@/lib/api";

export function usePredictions(vehicleId: number | null) {
  return useQuery({
    queryKey: ["predictions", vehicleId],
    queryFn: () => predictionApi.list(vehicleId!).then((r) => r.data),
    enabled: !!vehicleId,
  });
}

export function useRunPrediction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vehicleId: number) =>
      predictionApi.run(vehicleId).then((r) => r.data),
    onSuccess: (data, vehicleId) => {
      qc.invalidateQueries({ queryKey: ["predictions", vehicleId] });
      qc.invalidateQueries({ queryKey: ["dashboard", vehicleId] });
      qc.invalidateQueries({ queryKey: ["alerts", vehicleId] });
      qc.invalidateQueries({ queryKey: ["recommendations", vehicleId] });
    },
  });
}
