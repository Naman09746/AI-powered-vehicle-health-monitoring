"use client";

import { useQuery } from "@tanstack/react-query";
import { fleetApi } from "@/lib/api";

export function useFleet() {
  return useQuery({
    queryKey: ["fleet"],
    queryFn: () => fleetApi.overview().then((r) => r.data),
    refetchInterval: 30_000,
  });
}
