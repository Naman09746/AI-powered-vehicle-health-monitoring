"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { mlApi } from "@/lib/api";

export function useModels(vehicleId: number | null) {
  return useQuery({
    queryKey: ["models", vehicleId],
    queryFn: () => mlApi.models(vehicleId ?? undefined).then((r) => r.data),
    enabled: !!vehicleId,
  });
}

export function useTrainModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ vehicleId, tuningMode }: { vehicleId: number; tuningMode?: string }) =>
      mlApi.train(vehicleId, tuningMode).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["models"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["predictions"] });
    },
  });
}

export function usePromoteModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ modelId, vehicleId }: { modelId: number; vehicleId: number }) =>
      mlApi.promoteModel(modelId, vehicleId).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["models"] }),
  });
}
