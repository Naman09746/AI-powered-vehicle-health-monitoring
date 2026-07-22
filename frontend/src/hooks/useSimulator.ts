"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { simulatorApi } from "@/lib/api";

export function useSimulatorStatus(vehicleId: number | null) {
  return useQuery({
    queryKey: ["simulator", vehicleId],
    queryFn: () => simulatorApi.status(vehicleId!).then((r) => r.data),
    enabled: !!vehicleId,
    refetchInterval: (query) => (query.state.data as any)?.running ? 3_000 : false,
  });
}

export function useStartSimulation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      vehicleId,
      profile,
      interval,
    }: {
      vehicleId: number;
      profile?: string;
      interval?: number;
    }) => simulatorApi.start(vehicleId, profile, interval).then((r) => r.data),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["simulator", vars.vehicleId] });
      qc.invalidateQueries({ queryKey: ["dashboard", vars.vehicleId] });
    },
  });
}

export function useStopSimulation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vehicleId: number) =>
      simulatorApi.stop(vehicleId).then((r) => r.data),
    onSuccess: (data, vehicleId) => {
      qc.invalidateQueries({ queryKey: ["simulator", vehicleId] });
      qc.invalidateQueries({ queryKey: ["dashboard", vehicleId] });
    },
  });
}
