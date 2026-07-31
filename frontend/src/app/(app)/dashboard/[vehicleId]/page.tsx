"use client";

import { useParams } from "next/navigation";
import { useDashboard } from "@/hooks/useDashboard";
import { useAlerts } from "@/hooks/useAlerts";
import { PageHeader } from "@/components/shared/PageHeader";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { HealthGauge } from "@/components/charts/HealthGauge";
import { SensorTrendChart, sensorConfigs } from "@/components/charts/SensorTrendChart";
import { EmptyState } from "@/components/shared/EmptyState";
import { motion } from "framer-motion";
import { cn, formatNumber, getHealthColor } from "@/lib/utils";
import { AlertTriangle, Activity, Thermometer, Gauge, AlertCircle, CheckCircle, Wrench, UserCheck } from "lucide-react";
import { useState } from "react";



export default function DashboardPage() {
  const params = useParams();
  const vehicleId = Number(params.vehicleId);
  const { data, isLoading, error } = useDashboard(vehicleId);
  const { data: alerts } = useAlerts(vehicleId);
  const [activeSensor, setActiveSensor] = useState("engine_temp");

  if (isLoading) return <LoadingSpinner size="lg" />;

  if (error || !data) {
    return (
      <div>
        <PageHeader title="Dashboard" />
        <EmptyState
          icon={<Activity className="w-16 h-16" />}
          title="No data available"
          description="Upload sensor data or start the simulator to see the dashboard."
        />
      </div>
    );
  }

  const readings = data.recent_readings ?? [];
  const health = data.health_score ?? 0;
  const band = data.health_band;

  // Latest reading for metric cards
  const latest = readings[readings.length - 1] ?? {};

  return (
    <div>
      <PageHeader
        title={`${data.vehicle.vehicle_id_display}`}
        description={`${data.vehicle.model ?? "Vehicle"} • ${data.total_readings} readings • ${data.active_alerts} active alerts`}
      />

      {/* KPI Row */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8"
      >
        {[
          { label: "Health Score", value: `${health.toFixed(0)}%`, color: getHealthColor(health), icon: Gauge },
          { label: "Engine Temp", value: latest.engine_temp != null ? `${latest.engine_temp.toFixed(1)}°C` : "—", color: "#0ea5e9", icon: Thermometer },
          { label: "Active Alerts", value: data.active_alerts, color: data.active_alerts > 0 ? "#ef4444" : "#10b981", icon: AlertTriangle },
          { label: "Battery", value: latest.battery_voltage != null ? `${latest.battery_voltage.toFixed(1)}V` : "—", color: "#10b981", icon: Gauge },
        ].map((kpi) => (
          <div key={kpi.label} className="glass-card p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="metric-label">{kpi.label}</span>
              <kpi.icon className="w-4 h-4" style={{ color: kpi.color }} />
            </div>
            <div className="metric-value" style={{ color: kpi.color }}>{kpi.value}</div>
          </div>
        ))}
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Health Gauge */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1 }}
          className="glass-card p-6 flex items-center justify-center"
        >
          <div className="relative">
            <HealthGauge score={health} band={band} size="lg" />
          </div>
        </motion.div>

        {/* Sensor Summary */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="glass-card p-5 lg:col-span-2"
        >
          <h3 className="font-heading font-semibold text-text-primary mb-4">Sensor Summary</h3>
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(sensorConfigs).slice(0, 8).map(([key, cfg]) => {
              const val = (latest as Record<string, unknown>)[key] as number | null;
              const isNormal = val != null && val >= cfg.min && val <= cfg.max;
              return (
                <div
                  key={key}
                  className={cn(
                    "flex items-center justify-between p-3 rounded-lg border",
                    isNormal ? "border-accent-green/20 bg-accent-green/5" : "border-accent-red/20 bg-accent-red/5"
                  )}
                >
                  <span className="text-sm text-text-muted">{cfg.label}</span>
                  <span className={cn("text-sm font-medium", isNormal ? "text-accent-green" : "text-accent-red")}>
                    {val != null ? `${formatNumber(val)} ${cfg.unit}` : "—"}
                  </span>
                </div>
              );
            })}
          </div>
        </motion.div>
      </div>

      {/* Sensor Trend Chart */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="glass-card p-5"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-heading font-semibold text-text-primary">Sensor Trends</h3>
          <div className="flex gap-1">
            {Object.keys(sensorConfigs).slice(0, 6).map((s) => (
              <button
                key={s}
                onClick={() => setActiveSensor(s)}
                className={cn(
                  "px-2.5 py-1 text-xs rounded-md transition-colors",
                  activeSensor === s
                    ? "bg-accent-sky/10 text-accent-sky border border-accent-sky/20"
                    : "text-text-muted hover:text-text-primary border border-transparent"
                )}
                aria-label={`Show ${sensorConfigs[s].label} sensor trend`}
                aria-pressed={activeSensor === s}
              >
                {sensorConfigs[s].label.split(" ")[0]}
              </button>
            ))}
          </div>
        </div>
        <SensorTrendChart data={readings} sensor={activeSensor} />
      </motion.div>

      {/* Active OBD-II Fault Codes (DTCs) */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.22 }}
        className="glass-card p-5 mt-6"
      >
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-heading font-semibold text-text-primary flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-accent-amber" />
            Active OBD-II Fault Codes (DTCs)
          </h3>
          <span className="text-xs text-text-muted">
            {data.active_dtc_codes?.length ?? 0} active
          </span>
        </div>
        {!data.active_dtc_codes || data.active_dtc_codes.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-accent-green bg-accent-green/10 border border-accent-green/20 p-3 rounded-lg">
            <CheckCircle className="w-4 h-4" />
            <span>No active Diagnostic Trouble Codes (DTCs) detected. Vehicle operating cleanly.</span>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 gap-3">
            {data.active_dtc_codes.map((dtc: { code: string; description: string }) => (
              <div key={dtc.code} className="p-3 rounded-lg border border-accent-amber/30 bg-accent-amber/5 flex items-start gap-3">
                <span className="font-mono font-bold text-xs px-2.5 py-1 bg-accent-amber/20 text-accent-amber rounded border border-accent-amber/30">
                  {dtc.code}
                </span>
                <div className="text-xs">
                  <div className="font-semibold text-text-primary">{dtc.description}</div>
                  <div className="text-text-muted text-[11px] mt-0.5">OBD-II Diagnostic System</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </motion.div>


      {/* Driver Score & Maintenance Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        {/* Driver Behavior Score Card */}
        {data.driver_score && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.24 }}
            className="glass-card p-5"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-heading font-semibold text-text-primary flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-accent-sky" />
                Driver Behavior Analysis
              </h3>
              <span className="text-xs px-2.5 py-1 rounded bg-accent-sky/10 text-accent-sky border border-accent-sky/20 font-medium">
                {data.driver_score.rating}
              </span>
            </div>
            <div className="flex items-center justify-between p-4 rounded-xl bg-base-surface/40 border border-border/30 mb-4">
              <div>
                <div className="text-xs text-text-muted">Behavior Score</div>
                <div className="text-3xl font-extrabold font-heading text-accent-sky mt-0.5">
                  {data.driver_score.score}/100
                </div>
              </div>
              <div className="text-right text-xs space-y-1 text-text-muted">
                <div>Harsh Accel Events: <span className="font-semibold text-text-primary">{data.driver_score.harsh_acceleration_events}</span></div>
                <div>Over-Rev Events: <span className="font-semibold text-text-primary">{data.driver_score.over_rev_events}</span></div>
                <div>Excessive Idling: <span className="font-semibold text-text-primary">{data.driver_score.excessive_idle_count}</span></div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Upcoming Maintenance Schedule Card */}
        {data.upcoming_maintenance && data.upcoming_maintenance.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.26 }}
            className="glass-card p-5"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-heading font-semibold text-text-primary flex items-center gap-2">
                <Wrench className="w-4 h-4 text-accent-amber" />
                Upcoming Maintenance Forecast
              </h3>
              <span className="text-xs text-text-muted">Proactive Service</span>
            </div>
            <div className="space-y-2.5">
              {data.upcoming_maintenance.slice(0, 3).map((m: any, i: number) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg border border-border/30 bg-base-surface/40 text-xs">
                  <div className="font-medium text-text-primary">{m.service_type}</div>
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "px-2 py-0.5 rounded text-[11px] font-medium",
                      m.status === "overdue" ? "bg-accent-red/10 text-accent-red border border-accent-red/20" :
                      m.status === "due_soon" ? "bg-accent-amber/10 text-accent-amber border border-accent-amber/20" :
                      "bg-accent-green/10 text-accent-green border border-accent-green/20"
                    )}>
                      {m.urgency_msg}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </div>

      {/* Alerts */}

      {alerts && alerts.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="glass-card p-5 mt-6"
        >
          <h3 className="font-heading font-semibold text-text-primary mb-4">Recent Alerts</h3>
          <div className="space-y-2">
            {alerts.slice(0, 5).map((alert: { id: number; severity: string; message: string }) => (
              <div
                key={alert.id}
                className={cn(
                  "flex items-center gap-3 p-3 rounded-lg border",
                  alert.severity === "High" ? "border-accent-red/20 bg-accent-red/5" : "border-accent-amber/20 bg-accent-amber/5"
                )}
              >
                <AlertTriangle className={cn(
                  "w-4 h-4 flex-shrink-0",
                  alert.severity === "High" ? "text-accent-red" : "text-accent-amber"
                )} />
                <span className="text-sm text-text-primary flex-1">{alert.message}</span>
                <span className={cn(
                  "text-xs px-2 py-0.5 rounded",
                  alert.severity === "High" ? "bg-accent-red/10 text-accent-red" : "bg-accent-amber/10 text-accent-amber"
                )}>
                  {alert.severity}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}
