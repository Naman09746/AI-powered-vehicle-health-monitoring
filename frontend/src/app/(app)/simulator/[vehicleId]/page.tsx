"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/shared/PageHeader";
import { useVehicle } from "@/hooks/useVehicles";
import { useSimulatorStatus, useStartSimulation, useStopSimulation } from "@/hooks/useSimulator";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { useToast } from "@/store/toastStore";
import { motion } from "framer-motion";
import { Play, Square, Settings, Activity, Cpu, Thermometer, Clock, HelpCircle } from "lucide-react";
import { formatNumber } from "@/lib/utils";

export default function SimulatorPage() {
  const params = useParams();
  const vehicleId = Number(params.vehicleId);
  const toast = useToast();

  const { data: vehicle, isLoading: vehicleLoading } = useVehicle(vehicleId);
  const { data: status, isLoading: statusLoading } = useSimulatorStatus(vehicleId);
  const startMutation = useStartSimulation();
  const stopMutation = useStopSimulation();

  const [profile, setProfile] = useState("healthy");
  const [interval, setIntervalValue] = useState(3);

  if (vehicleLoading || statusLoading) {
    return <LoadingSpinner size="lg" />;
  }

  if (!vehicle) {
    return (
      <div>
        <PageHeader title="Telemetry Simulator" />
        <div className="glass-card p-8 text-center text-text-muted">
          Vehicle not found. Please register or select a valid vehicle.
        </div>
      </div>
    );
  }

  const handleStart = async () => {
    try {
      await startMutation.mutateAsync({
        vehicleId,
        profile,
        interval,
      });
      toast.add("Telemetry simulation started", "success");
    } catch (err: any) {
      toast.add(err.response?.data?.detail ?? "Failed to start simulation", "error");
    }
  };

  const handleStop = async () => {
    try {
      await stopMutation.mutateAsync(vehicleId);
      toast.add("Telemetry simulation stopped", "success");
    } catch (err: any) {
      toast.add(err.response?.data?.detail ?? "Failed to stop simulation", "error");
    }
  };

  const isRunning = status?.running ?? false;

  return (
    <div>
      <PageHeader
        title={`${vehicle.vehicle_id_display} Simulator`}
        description={`Simulate live sensor telemetry for ${vehicle.model ?? "Vehicle"} (ID: ${vehicle.id})`}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Configuration Panel */}
        <div className="lg:col-span-1 space-y-6">
          <div className="glass-card p-6">
            <h2 className="font-heading font-semibold text-text-primary mb-4 flex items-center gap-2">
              <Settings className="w-5 h-5 text-accent-sky" />
              Simulation Settings
            </h2>

            <div className="space-y-4">
              <div>
                <label htmlFor="sim-profile" className="block text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">
                  Operating Profile
                </label>
                <select
                  id="sim-profile"
                  className="input-field w-full"
                  value={profile}
                  onChange={(e) => setProfile(e.target.value)}
                  disabled={isRunning}
                >
                  <option value="healthy">Healthy (Optimal Behavior)</option>
                  <option value="degrading">Degrading (Gradual Wear)</option>
                  <option value="critical">Critical (Imminent Failure)</option>
                  <option value="intermittent_fault">Intermittent Faults</option>
                </select>
                <p className="text-[11px] text-text-muted mt-1.5">
                  Determines the distribution and drift of generated sensor readings.
                </p>
              </div>

              <div>
                <label htmlFor="sim-interval" className="block text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">
                  Broadcast Interval (seconds)
                </label>
                <div className="flex items-center gap-3">
                  <input
                    id="sim-interval"
                    type="range"
                    min="1"
                    max="10"
                    step="1"
                    className="flex-1 accent-accent-sky"
                    value={interval}
                    onChange={(e) => setIntervalValue(Number(e.target.value))}
                    disabled={isRunning}
                  />
                  <span className="font-semibold text-text-primary min-w-[24px] text-center">{interval}s</span>
                </div>
              </div>

              <div className="pt-4 border-t border-border/30">
                {isRunning ? (
                  <button
                    onClick={handleStop}
                    disabled={stopMutation.isPending}
                    className="w-full btn-ghost border border-accent-red/20 bg-accent-red/5 text-accent-red hover:bg-accent-red/10 flex items-center justify-center gap-2"
                  >
                    <Square className="w-4 h-4 fill-accent-red" />
                    Stop Simulation
                  </button>
                ) : (
                  <button
                    onClick={handleStart}
                    disabled={startMutation.isPending}
                    className="w-full btn-primary flex items-center justify-center gap-2"
                  >
                    <Play className="w-4 h-4 fill-white" />
                    Start Simulation
                  </button>
                )}
              </div>
            </div>
          </div>

          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-2 flex items-center gap-1.5">
              <Clock className="w-4 h-4 text-text-muted" />
              Real-time Ingestion
            </h3>
            <p className="text-xs text-text-muted leading-relaxed">
              When started, this simulator broadcasts telemetry data to the API and WebSocket feed.
              It directly mimics physical vehicle engine control units (ECUs) without requiring external hardware.
            </p>
          </div>
        </div>

        {/* Right: Live Telemetry Output Monitor */}
        <div className="lg:col-span-2 space-y-6">
          <div className="glass-card p-6 min-h-[360px] flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="font-heading font-semibold text-text-primary flex items-center gap-2">
                  <Cpu className="w-5 h-5 text-accent-sky" />
                  Live Output Monitor
                </h2>
                <div className="flex items-center gap-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${isRunning ? "bg-accent-green animate-pulse" : "bg-text-muted/30"}`} />
                  <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                    {isRunning ? `Running (${status?.profile})` : "Stopped"}
                  </span>
                </div>
              </div>

              {isRunning && status?.last_reading ? (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
                  {[
                    { label: "Engine Temp", val: status.last_reading.engine_temp, unit: "°C" },
                    { label: "Oil Pressure", val: status.last_reading.oil_pressure, unit: "kPa" },
                    { label: "Coolant Temp", val: status.last_reading.coolant_temp, unit: "°C" },
                    { label: "Engine RPM", val: status.last_reading.engine_rpm, unit: "rpm" },
                    { label: "Vibration", val: status.last_reading.vibration, unit: "mm/s" },
                    { label: "Battery Voltage", val: status.last_reading.battery_voltage, unit: "V" },
                  ].map((s) => (
                    <div key={s.label} className="p-3.5 rounded-lg border border-border/30 bg-base-elevated/40">
                      <div className="text-[11px] text-text-muted uppercase mb-1">{s.label}</div>
                      <div className="text-base font-semibold text-text-primary">
                        {s.val != null ? `${formatNumber(s.val)} ${s.unit}` : "—"}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-48 border border-dashed border-border/40 rounded-xl">
                  <Activity className="w-10 h-10 text-text-muted/30 mb-2" />
                  <p className="text-sm text-text-muted">Start the simulation to stream telemetry outputs here.</p>
                </div>
              )}
            </div>

            {isRunning && (
              <div className="pt-4 border-t border-border/30 flex items-center justify-between text-xs text-text-muted">
                <span>Active Ticks: <strong className="text-text-primary">{status?.tick ?? 0}</strong></span>
                <span>Send rate: <strong className="text-text-primary">Every {status?.interval ?? interval}s</strong></span>
              </div>
            )}
          </div>

          {isRunning && status?.last_reading && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-5">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">RAW JSON Payload</h3>
              <pre className="text-[11px] font-mono text-accent-sky bg-base-surface/40 p-3 rounded-lg border border-border/20 overflow-x-auto max-h-40">
                {JSON.stringify(status.last_reading, null, 2)}
              </pre>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
