"use client";
import { useParams } from "next/navigation";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { useModels, useTrainModel, usePromoteModel } from "@/hooks/useML";
import { useToast } from "@/store/toastStore";
import { useQueryClient } from "@tanstack/react-query";
import { mlApi } from "@/lib/api";
import { motion } from "framer-motion";
import { Brain, Zap, Trophy, BarChart3, AlertTriangle, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useState, useCallback } from "react";
import type { TrainedModel } from "@/lib/validation";
import { NextStepCard } from "@/components/shared/NextStepCard";

export default function TrainingPage() {
  const params = useParams();
  const vehicleId = Number(params.vehicleId);
  const { data: models, isLoading, refetch } = useModels(vehicleId);
  const train = useTrainModel();
  const promote = usePromoteModel();
  const queryClient = useQueryClient();
  const toast = useToast();

  const handleDeleteModel = useCallback(async (modelId: number) => {
    if (!confirm("Are you sure you want to delete this model?")) return;
    try {
      await mlApi.deleteModel(modelId);
      toast.add("Model deleted successfully", "success");
      queryClient.invalidateQueries({ queryKey: ["models", vehicleId] });
      refetch();
    } catch {
      toast.add("Failed to delete model", "error");
    }
  }, [vehicleId, toast, queryClient, refetch]);
  const [tuning, setTuning] = useState("quick");
  const [trainedSuccessfully, setTrainedSuccessfully] = useState(false);

  if (isLoading) return <LoadingSpinner size="lg" />;

  const handleTrain = async () => {
    setTrainedSuccessfully(false);
    try {
      const r = await train.mutateAsync({ vehicleId, tuningMode: tuning });
      toast.add(`Model trained: ${r.best_model}`, "success");
      setTrainedSuccessfully(true);
    } catch { toast.add("Training failed", "error"); }
  };

  const handlePromote = async (modelId: number) => {
    try { await promote.mutateAsync({ modelId, vehicleId }); toast.add("Champion promoted", "success"); }
    catch { toast.add("Failed to promote", "error"); }
  };

  if (!models || models.length === 0) {
    return (
      <div>
        <PageHeader title="ML Training" description="Train ML models on sensor data" actions={
          <div className="flex gap-2">
            <select value={tuning} onChange={(e) => setTuning(e.target.value)} className="input-field w-32" aria-label="Training mode">
              <option value="quick">Quick</option><option value="thorough">Thorough</option>
            </select>
            <button onClick={handleTrain} disabled={train.isPending} className="btn-primary">
              {train.isPending ? <span className="flex items-center gap-2"><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Training...</span> : <span className="flex items-center gap-2"><Zap className="w-4 h-4" /> Train</span>}
            </button>
          </div>
        } />
        {trainedSuccessfully && (
          <div className="mb-6">
            <NextStepCard
              title="ML Model Trained Successfully"
              description="Your predictive model has been trained and evaluated. The next step is to run predictions against the new model to assess the risk of vehicle failures."
              href={`/predictions/${vehicleId}`}
              actionLabel="Run Failure Predictions"
              icon={BarChart3}
            />
          </div>
        )}
        <EmptyState icon={<Brain className="w-16 h-16" />} title="No trained models yet" description="Upload sensor data first, then train classifiers to predict failures." />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="ML Training" description={`${models.length} model${models.length > 1 ? "s" : ""} trained`} actions={
        <div className="flex gap-2">
          <select value={tuning} onChange={(e) => setTuning(e.target.value)} className="input-field w-32" aria-label="Training mode">
            <option value="quick">Quick</option><option value="thorough">Thorough</option>
          </select>
          <button onClick={handleTrain} disabled={train.isPending} className="btn-primary">
            {train.isPending ? "Training..." : <span className="flex items-center gap-2"><Zap className="w-4 h-4" /> Train</span>}
          </button>
        </div>
      } />
      
      {trainedSuccessfully && (
        <div className="mb-6">
          <NextStepCard
            title="ML Model Trained Successfully"
            description="Your predictive model has been trained and evaluated. The next step is to run predictions against the new model to assess the risk of vehicle failures."
            href={`/predictions/${vehicleId}`}
            actionLabel="Run Failure Predictions"
            icon={BarChart3}
          />
        </div>
      )}

      <div className="space-y-3">
        {models.map((m: TrainedModel, i: number) => (
          <motion.div key={m.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
            className={cn("glass-card p-5 flex items-center justify-between", m.is_champion && "border-accent-sky/40")}>
            <div className="flex items-center gap-4">
              <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center", m.is_champion ? "bg-accent-sky/10" : "bg-base-elevated")}>
                {m.is_champion ? <Trophy className="w-5 h-5 text-accent-sky" /> : <BarChart3 className="w-5 h-5 text-text-muted" />}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-heading font-semibold text-text-primary">{m.model_name}</span>
                  {m.is_champion && <span className="badge-low text-[10px]">CHAMPION</span>}
                </div>
                <div className="text-xs text-text-muted flex gap-3 mt-0.5">
                  <span>Acc: {m.accuracy != null ? `${(m.accuracy * 100).toFixed(1)}%` : "—"}</span>
                  <span>F1: {m.f1 != null ? `${(m.f1 * 100).toFixed(1)}%` : "—"}</span>
                  {m.trained_at && <span>{new Date(m.trained_at).toLocaleDateString()}</span>}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {!m.is_champion && (
                <button onClick={() => handlePromote(m.id)} className="btn-secondary text-xs px-3 py-1.5" aria-label={`Promote ${m.model_name} to champion`}>
                  Promote
                </button>
              )}
              <button
                onClick={() => handleDeleteModel(m.id)}
                className="text-text-muted hover:text-red-500 transition-colors p-2 rounded-md hover:bg-red-500/10"
                title="Delete Model"
                aria-label={`Delete model ${m.model_name}`}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
