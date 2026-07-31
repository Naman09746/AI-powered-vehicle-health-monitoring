"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCreateVehicle } from "@/hooks/useVehicles";
import { useToast } from "@/store/toastStore";
import { api } from "@/lib/api";
import { Truck, Activity, CheckCircle2, ArrowRight, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function OnboardingPage() {
  const router = useRouter();
  const toast = useToast();
  const createVehicle = useCreateVehicle();
  const [step, setStep] = useState(1);
  const [vehicleForm, setVehicleForm] = useState({
    vehicle_id_display: "VH-DEMO-001",
    model: "Toyota Camry Hybrid",
    manufacturing_year: 2024,
    engine_type: "Hybrid",
  });
  const [createdVehicleId, setCreatedVehicleId] = useState<number | null>(null);

  const handleStep1 = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await createVehicle.mutateAsync(vehicleForm);
      setCreatedVehicleId(res.id);
      toast.add(`Registered vehicle ${res.vehicle_id_display}!`, "success");
      setStep(2);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.add(detail ?? "Vehicle registration failed", "error");
    }
  };

  const handleFinish = async () => {
    try {
      await api.post("/auth/complete-onboarding");
    } catch {
      // Ignore if endpoint fails
    }
    router.replace(createdVehicleId ? `/dashboard/${createdVehicleId}` : "/fleet");
  };

  return (
    <div className="max-w-3xl mx-auto py-10 px-4">
      {/* Progress Steps Header */}
      <div className="flex items-center justify-between mb-10">
        {[
          { num: 1, label: "Add First Vehicle", icon: Truck },
          { num: 2, label: "Telemetry Connection", icon: Activity },
          { num: 3, label: "Ready to Monitor", icon: CheckCircle2 },
        ].map((s) => (
          <div key={s.num} className="flex items-center gap-3">
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center font-heading font-bold text-sm transition-colors ${
                step >= s.num
                  ? "bg-accent-sky text-white shadow-[0_0_15px_rgba(14,165,233,0.3)]"
                  : "bg-base-surface text-text-muted border border-border"
              }`}
            >
              <s.icon className="w-5 h-5" />
            </div>
            <span
              className={`text-sm font-medium hidden sm:inline ${
                step >= s.num ? "text-text-primary" : "text-text-muted"
              }`}
            >
              {s.label}
            </span>
          </div>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {step === 1 && (
          <motion.div
            key="step1"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="glass-card p-8"
          >
            <div className="flex items-center gap-3 mb-2">
              <Sparkles className="w-6 h-6 text-accent-sky" />
              <h2 className="text-2xl font-bold font-heading">Welcome to Vehicle Health Monitor</h2>
            </div>
            <p className="text-text-muted text-sm mb-6">
              Let's set up your first vehicle to start tracking OBD-II sensors and AI failure predictions.
            </p>

            <form onSubmit={handleStep1} className="space-y-4">
              <div>
                <label htmlFor="vhId" className="block text-xs text-text-muted mb-1">Vehicle Display ID *</label>
                <input
                  id="vhId"
                  className="input-field"
                  value={vehicleForm.vehicle_id_display}
                  onChange={(e) => setVehicleForm({ ...vehicleForm, vehicle_id_display: e.target.value })}
                  placeholder="e.g. VH-001 or TRUCK-99"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="vhModel" className="block text-xs text-text-muted mb-1">Model Name</label>
                  <input
                    id="vhModel"
                    className="input-field"
                    value={vehicleForm.model}
                    onChange={(e) => setVehicleForm({ ...vehicleForm, model: e.target.value })}
                    placeholder="e.g. Toyota Camry"
                  />
                </div>
                <div>
                  <label htmlFor="vhYear" className="block text-xs text-text-muted mb-1">Year</label>
                  <input
                    id="vhYear"
                    type="number"
                    className="input-field"
                    value={vehicleForm.manufacturing_year}
                    onChange={(e) => setVehicleForm({ ...vehicleForm, manufacturing_year: Number(e.target.value) })}
                    min={1990}
                    max={2030}
                  />
                </div>
              </div>
              <div>
                <label htmlFor="vhEng" className="block text-xs text-text-muted mb-1">Engine Type</label>
                <select
                  id="vhEng"
                  className="input-field"
                  value={vehicleForm.engine_type}
                  onChange={(e) => setVehicleForm({ ...vehicleForm, engine_type: e.target.value })}
                >
                  <option>Gasoline</option>
                  <option>Diesel</option>
                  <option>Hybrid</option>
                  <option>Electric</option>
                </select>
              </div>

              <div className="pt-4 flex justify-end">
                <button type="submit" disabled={createVehicle.isPending} className="btn-primary flex items-center gap-2">
                  <span>{createVehicle.isPending ? "Registering..." : "Continue to Step 2"}</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </form>
          </motion.div>
        )}

        {step === 2 && (
          <motion.div
            key="step2"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="glass-card p-8 text-center"
          >
            <div className="w-16 h-16 rounded-2xl bg-accent-sky/10 border border-accent-sky/20 flex items-center justify-center mx-auto mb-4 text-accent-sky">
              <Activity className="w-8 h-8 animate-pulse" />
            </div>

            <h2 className="text-2xl font-bold font-heading mb-2">Connecting Telemetry Stream</h2>
            <p className="text-text-muted text-sm max-w-md mx-auto mb-6">
              Your vehicle <strong>{vehicleForm.vehicle_id_display}</strong> is now registered. You can stream OBD-II telemetry via HTTP REST or launch the simulator anytime.
            </p>

            <div className="p-4 rounded-xl bg-base border border-border/50 font-mono text-xs text-left max-w-md mx-auto mb-6 space-y-1 text-text-muted">
              <div className="text-accent-sky"># Ingestion Endpoint Ready</div>
              <div>POST /api/v1/vehicles/{createdVehicleId}/readings</div>
              <div className="text-accent-green">✓ Health score & DTC parser active</div>
            </div>

            <button onClick={() => setStep(3)} className="btn-primary px-8">
              Proceed to Dashboard <ArrowRight className="w-4 h-4 ml-2" />
            </button>
          </motion.div>
        )}

        {step === 3 && (
          <motion.div
            key="step3"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="glass-card p-8 text-center"
          >
            <div className="w-16 h-16 rounded-full bg-accent-green/10 border border-accent-green/20 flex items-center justify-center mx-auto mb-4 text-accent-green">
              <CheckCircle2 className="w-8 h-8" />
            </div>

            <h2 className="text-2xl font-bold font-heading mb-2">Setup Complete!</h2>
            <p className="text-text-muted text-sm max-w-md mx-auto mb-8">
              Your fleet environment is fully configured. Launch into your interactive dashboard to track sensor trends and failure risks.
            </p>

            <button onClick={handleFinish} className="btn-primary px-8 py-3 text-base">
              Open Vehicle Dashboard <ArrowRight className="w-5 h-5 ml-2" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
