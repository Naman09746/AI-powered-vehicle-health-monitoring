"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { alertApi } from "@/lib/api";

export function useAlerts(vehicleId: number | null) {
  return useQuery({
    queryKey: ["alerts", vehicleId],
    queryFn: () => alertApi.list(vehicleId!).then((r) => r.data),
    enabled: !!vehicleId,
    refetchInterval: 15_000,
  });
}

export function useDismissAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (alertId: number) => alertApi.dismiss(alertId).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
      qc.invalidateQueries({ queryKey: ["recommendations"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
