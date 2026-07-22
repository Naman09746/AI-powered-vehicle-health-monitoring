"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { vehicleApi } from "@/lib/api";

export function useVehicles() {
  return useQuery({
    queryKey: ["vehicles"],
    queryFn: () => vehicleApi.list().then((r) => r.data),
  });
}

export function useVehicle(id: number | null) {
  return useQuery({
    queryKey: ["vehicle", id],
    queryFn: () => vehicleApi.get(id!).then((r) => r.data),
    enabled: !!id,
  });
}

export function useCreateVehicle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof vehicleApi.create>[0]) =>
      vehicleApi.create(data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["vehicles"] });
      qc.invalidateQueries({ queryKey: ["fleet"] });
    },
  });
}

export function useDeleteVehicle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => vehicleApi.delete(id).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["vehicles"] });
      qc.invalidateQueries({ queryKey: ["fleet"] });
    },
  });
}

