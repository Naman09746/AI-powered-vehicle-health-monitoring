"use client";

import { useEffect } from "react";
import { useToast } from "@/store/toastStore";
import { getApiWsUrl } from "@/lib/api";

/**
 * Global hook to listen for real-time WebSocket alerts and telemetry
 * and show in-app toast notifications.
 */
export function useAlertToasts(vehicleId: number | null) {
  const toast = useToast();

  useEffect(() => {
    if (!vehicleId) return;

    const wsUrl = getApiWsUrl(vehicleId);
    let ws: WebSocket | null = null;

    try {
      ws = new WebSocket(wsUrl);

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Check for critical health score or high alert
          if (data.health_score !== undefined && data.health_score < 45) {
            toast.add(
              `Critical Health Warning: Vehicle score dropped to ${data.health_score}/100!`,
              "error"
            );
          } else if (data.alerts_generated && data.alerts_generated > 0) {
            toast.add(
              `Alert generated for Vehicle (alerts: ${data.alerts_generated})`,
              "info"
            );
          }
        } catch {
          // Ignore JSON parse errors
        }
      };

      ws.onerror = () => {
        // Silently handle WS connection errors
      };
    } catch {
      // WS failover handled gracefully
    }

    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, [vehicleId, toast]);
}
