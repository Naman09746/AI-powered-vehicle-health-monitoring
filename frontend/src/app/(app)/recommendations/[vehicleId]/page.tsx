"use client";

import { useParams } from "next/navigation";
import { PageHeader } from "@/components/shared/PageHeader";
import { useRecommendations } from "@/hooks/useRecommendations";
import { useDismissAlert } from "@/hooks/useAlerts";
import { EmptyState } from "@/components/shared/EmptyState";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { useToast } from "@/store/toastStore";
import { motion } from "framer-motion";
import { Bell, AlertTriangle, CheckCircle, EyeOff, ShieldAlert, ArrowRight, Gauge } from "lucide-react";
import { cn } from "@/lib/utils";

export default function RecommendationsPage() {
  const params = useParams();
  const vehicleId = Number(params.vehicleId);
  const toast = useToast();

  const { data, isLoading, error } = useRecommendations(vehicleId);
  const dismissMutation = useDismissAlert();

  const handleDismiss = async (alertId: number) => {
    try {
      await dismissMutation.mutateAsync(alertId);
      toast.add("Alert dismissed", "success");
    } catch {
      toast.add("Failed to dismiss alert", "error");
    }
  };

  if (isLoading) return <LoadingSpinner size="lg" />;

  const recommendations = data?.recommendations ?? [];
  const alerts = data?.alerts ?? [];
  const deviations = data?.deviations ?? [];

  const hasContent = alerts.length > 0 || deviations.length > 0;

  return (
    <div>
      <PageHeader
        title="Alerts & Recommendations"
        description="AI-diagnosed sensor deviations and active maintenance alerts"
      />

      {!hasContent ? (
        <EmptyState
          icon={<Bell className="w-16 h-16" />}
          title="All systems optimal"
          description="No active alerts or anomalous sensor deviations detected for this vehicle."
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Active Alerts */}
          <div className="space-y-4">
            <h2 className="font-heading font-semibold text-text-primary text-base flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-accent-red" />
              Active System Alerts ({alerts.length})
            </h2>

            {alerts.length === 0 ? (
              <div className="glass-card p-5 text-center text-text-muted text-sm">
                No active system alerts.
              </div>
            ) : (
              <div className="space-y-3" role="list" aria-label="Active alerts">
                {alerts.map((alert: any, i: number) => (
                  <motion.div
                    key={alert.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className={cn(
                      "p-4 rounded-xl border flex items-start gap-4 bg-base-elevated/20 transition-all",
                      alert.severity === "High"
                        ? "border-accent-red/20 hover:border-accent-red/40"
                        : "border-accent-amber/20 hover:border-accent-amber/40"
                    )}
                    role="listitem"
                  >
                    <AlertTriangle
                      className={cn(
                        "w-5 h-5 mt-0.5 flex-shrink-0",
                        alert.severity === "High" ? "text-accent-red" : "text-accent-amber"
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="font-semibold text-sm text-text-primary">
                          {alert.alert_type}
                        </span>
                        <span
                          className={cn(
                            "text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded",
                            alert.severity === "High"
                              ? "bg-accent-red/10 text-accent-red"
                              : "bg-accent-amber/10 text-accent-amber"
                          )}
                        >
                          {alert.severity}
                        </span>
                      </div>
                      <p className="text-sm text-text-muted leading-normal">{alert.message}</p>
                    </div>
                    <button
                      onClick={() => handleDismiss(alert.id)}
                      disabled={dismissMutation.isPending}
                      className="btn-ghost p-1.5 rounded-lg opacity-70 hover:opacity-100 hover:bg-base-elevated/40 self-center"
                      title="Dismiss alert"
                      aria-label={`Dismiss ${alert.alert_type} alert`}
                    >
                      <EyeOff className="w-4 h-4" />
                    </button>
                  </motion.div>
                ))}
              </div>
            )}
          </div>

          {/* Sensor Deviations */}
          <div className="space-y-4">
            <h2 className="font-heading font-semibold text-text-primary text-base flex items-center gap-2">
              <Gauge className="w-5 h-5 text-accent-sky" />
              Anomalous Sensor Deviations ({deviations.length})
            </h2>

            {deviations.length === 0 ? (
              <div className="glass-card p-5 text-center text-text-muted text-sm">
                All telemetry sensors are reading within normal thresholds.
              </div>
            ) : (
              <div className="space-y-3">
                {deviations.map((dev: any, i: number) => (
                  <motion.div
                    key={dev.sensor}
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="p-4 rounded-xl border border-border/40 bg-base-elevated/20 flex flex-col gap-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-sm text-text-primary">{dev.label}</span>
                      <span className="text-[11px] font-semibold text-accent-red px-2 py-0.5 rounded-full bg-accent-red/5 border border-accent-red/10">
                        +{dev.deviation_pct.toFixed(0)}% Out of Bounds
                      </span>
                    </div>

                    <div className="flex items-center gap-4 text-xs text-text-muted bg-base-surface/40 p-2.5 rounded-lg border border-border/20">
                      <div>
                        Current: <strong className="text-text-primary">{dev.value.toFixed(1)} {dev.unit}</strong>
                      </div>
                      <ArrowRight className="w-3.5 h-3.5 text-text-muted/40" />
                      <div>
                        Normal Range: <strong className="text-text-primary">{dev.normal_range}</strong>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
