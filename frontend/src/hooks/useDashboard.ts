"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { API_BASE_URL, dashboardApi } from "@/lib/api";
import { useSSE } from "@/hooks/useSSE";
import { useAuthStore } from "@/store/authStore";
import type { DashboardData } from "@/lib/validation";

/**
 * Dashboard data hook — SSE live updates + polling fallback.
 *
 * SSE silently updates the TanStack Query cache so the UI stays reactive
 * without manual state management.
 */
export function useDashboard(vehicleId: number | null) {
  const queryClient = useQueryClient();
  const token = useAuthStore((s) => s.token);

  // SSE: live sensor feed — silently update cache
  const sseUrl = vehicleId && token
    ? `${API_BASE_URL}/dashboard/${vehicleId}/stream?token=${encodeURIComponent(token)}`
    : null;

  const handleSSEMessage = useCallback(
    (data: unknown) => {
      if (data && typeof data === "object" && vehicleId) {
        queryClient.setQueryData(["dashboard", vehicleId], data);
      }
    },
    [queryClient, vehicleId]
  );

  const sse = useSSE<DashboardData>(sseUrl, {
    onMessage: handleSSEMessage,
  });

  const query = useQuery<DashboardData>({
    queryKey: ["dashboard", vehicleId],
    queryFn: () => dashboardApi.get(vehicleId!).then((r) => r.data),
    enabled: !!vehicleId,
    refetchInterval: sse.status === "connected" ? false : 30_000,
  });

  return {
    ...query,
    isLive: sse.status === "connected",
    sseStatus: sse.status,
  };
}
