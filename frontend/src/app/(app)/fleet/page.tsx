"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useVehicles, useCreateVehicle } from "@/hooks/useVehicles";
import { useFleet } from "@/hooks/useFleet";
import { useAuthStore } from "@/store/authStore";
import { useToast } from "@/store/toastStore";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { cn, getHealthColor } from "@/lib/utils";
import type { Vehicle } from "@/lib/validation";
import { motion } from "framer-motion";
import { Truck, Plus, Activity, AlertTriangle, CheckCircle, X } from "lucide-react";

export default function FleetPage() {
  const router = useRouter();
  const { data: vehicles, isLoading: vLoading } = useVehicles();
  const { data: fleet, isLoading: fLoading } = useFleet();
  const setSelectedVehicle = useAuthStore((s) => s.setSelectedVehicle);
  const createVehicle = useCreateVehicle();
  const toast = useToast();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ vehicle_id_display: "", model: "", manufacturing_year: 2026, engine_type: "Gasoline" });

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.vehicle_id_display.trim()) { toast.add("Vehicle ID is required", "error"); return; }
    try {
      await createVehicle.mutateAsync(form);
      toast.add(`Vehicle ${form.vehicle_id_display} registered`, "success");
      setShowForm(false);
      setForm({ vehicle_id_display: "", model: "", manufacturing_year: 2026, engine_type: "Gasoline" });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.add(detail ?? "Failed to register vehicle", "error");
    }
  };

  if (vLoading || fLoading) return <LoadingSpinner size="lg" />;

  const vehicleList = Array.isArray(vehicles) ? vehicles : [];

  return (
    <div>
      <PageHeader
        title="Fleet Overview"
        description={`${fleet?.vehicle_count ?? vehicleList.length} vehicle${vehicleList.length !== 1 ? "s" : ""} monitored`}
        actions={
          <button onClick={() => setShowForm(!showForm)} className="btn-primary flex items-center gap-2">
            {showForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
            {showForm ? "Cancel" : "Add Vehicle"}
          </button>
        }
      />

      {/* Register Vehicle Form */}
      {showForm && (
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-5 mb-6">
          <h3 className="font-heading font-semibold text-text-primary mb-4">Register New Vehicle</h3>
          <form onSubmit={handleCreate} className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            <div>
              <label htmlFor="vId" className="block text-xs text-text-muted mb-1">Vehicle ID *</label>
              <input id="vId" className="input-field" placeholder="VH-001" value={form.vehicle_id_display} onChange={(e) => setForm({ ...form, vehicle_id_display: e.target.value })} required />
            </div>
            <div>
              <label htmlFor="vModel" className="block text-xs text-text-muted mb-1">Model</label>
              <input id="vModel" className="input-field" placeholder="Toyota Camry" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />
            </div>
            <div>
              <label htmlFor="vYear" className="block text-xs text-text-muted mb-1">Year</label>
              <input id="vYear" type="number" className="input-field" value={form.manufacturing_year} onChange={(e) => setForm({ ...form, manufacturing_year: Number(e.target.value) })} min={1990} max={2027} />
            </div>
            <div>
              <label htmlFor="vEngine" className="block text-xs text-text-muted mb-1">Engine</label>
              <select id="vEngine" className="input-field" value={form.engine_type} onChange={(e) => setForm({ ...form, engine_type: e.target.value })}>
                <option>Gasoline</option><option>Diesel</option><option>Hybrid</option><option>Electric</option>
              </select>
            </div>
            <div className="flex items-end">
              <button type="submit" disabled={createVehicle.isPending} className="btn-primary w-full">
                {createVehicle.isPending ? "Registering..." : "Register"}
              </button>
            </div>
          </form>
        </motion.div>
      )}

      {vehicleList.length === 0 && !showForm ? (
        <EmptyState
          icon={<Truck className="w-16 h-16" />}
          title="No vehicles registered"
          description='Click "Add Vehicle" above to register your first vehicle.'
        />
      ) : (
        <>
          {/* KPI Cards */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {[
              { label: "Total Vehicles", value: fleet?.vehicle_count ?? vehicleList.length, icon: Truck, color: "#0ea5e9" },
              { label: "Avg Health Score", value: fleet?.avg_health_score != null ? `${fleet.avg_health_score.toFixed(0)}%` : "—", icon: Activity, color: getHealthColor(fleet?.avg_health_score ?? 0) },
              { label: "Active Alerts", value: fleet?.total_active_alerts ?? 0, icon: AlertTriangle, color: "#ef4444" },
              { label: "Healthy", value: fleet?.healthy_count ?? 0, icon: CheckCircle, color: "#10b981" },
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

          {/* Fleet Health Distribution */}
          {fleet && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass-card p-5 mb-8">
              <h3 className="font-heading font-semibold text-text-primary mb-4">Fleet Health Distribution</h3>
              <div className="flex gap-1 h-3 rounded-full overflow-hidden">
                <div className="bg-accent-green transition-all duration-500" style={{ flex: fleet.healthy_count || 0.1 }} />
                <div className="bg-accent-amber transition-all duration-500" style={{ flex: fleet.at_risk_count || 0.1 }} />
                <div className="bg-accent-red transition-all duration-500" style={{ flex: fleet.critical_count || 0.1 }} />
              </div>
              <div className="flex gap-6 mt-3 text-xs text-text-muted">
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-accent-green" /> Healthy ({fleet.healthy_count})</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-accent-amber" /> At risk ({fleet.at_risk_count})</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-accent-red" /> Critical ({fleet.critical_count})</span>
              </div>
            </motion.div>
          )}

          {/* Vehicle list */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            <h3 className="font-heading font-semibold text-text-primary mb-4">All Vehicles</h3>
            <div className="space-y-3">
              {vehicleList.map((v: Vehicle, i: number) => (
                <motion.div key={v.id} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.05 * i }}
                  className="glass-card-hover p-5 cursor-pointer focus-visible:ring-2 focus-visible:ring-accent-sky focus-visible:ring-offset-2 focus-visible:outline-none"
                  role="button" tabIndex={0}
                  aria-label={`View dashboard for ${v.vehicle_id_display}${v.model ? `, ${v.model}` : ""}`}
                  onClick={() => { setSelectedVehicle(v.id); router.push(`/dashboard/${v.id}`); }}
                  onKeyDown={(e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelectedVehicle(v.id); router.push(`/dashboard/${v.id}`); } }}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-accent-sky/10 border border-accent-sky/20 flex items-center justify-center" aria-hidden="true">
                        <Truck className="w-5 h-5 text-accent-sky" />
                      </div>
                      <div>
                        <div className="font-heading font-semibold text-text-primary">{v.vehicle_id_display}</div>
                        <div className="text-sm text-text-muted">{v.model ?? "Unknown model"} • {v.manufacturing_year ?? "—"}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 text-sm text-text-muted">
                      <span>{v.engine_type ?? "—"}</span>
                      <span className="w-1.5 h-1.5 rounded-full bg-border" aria-hidden="true" />
                      <span>{v.mileage ? `${v.mileage.toLocaleString()} km` : "—"}</span>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </>
      )}
    </div>
  );
}
