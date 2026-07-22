"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { usePredictions, useRunPrediction } from "@/hooks/usePredictions";
import { useDashboard } from "@/hooks/useDashboard";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { HealthGauge } from "@/components/charts/HealthGauge";
import { motion } from "framer-motion";
import { cn, formatNumber, getFailureColor, getHealthColor } from "@/lib/utils";
import type { PredictionResult } from "@/lib/validation";
import { AlertTriangle, CheckCircle, BarChart3, Zap, Activity, Bell } from "lucide-react";
import { NextStepCard } from "@/components/shared/NextStepCard";

export default function PredictionsPage() {
  const params = useParams();
  const vehicleId = Number(params.vehicleId);
  const { data: dashboard } = useDashboard(vehicleId);
  const { data: predictions, isLoading } = usePredictions(vehicleId);
  const runMutation = useRunPrediction();
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [running, setRunning] = useState(false);

  const handleRun = async () => {
    setRunning(true);
    try {
      const data = await runMutation.mutateAsync(vehicleId);
      setResult(data);
    } catch (err) {
      console.error("Prediction failed", err);
    } finally {
      setRunning(false);
    }
  };

  if (isLoading) return <LoadingSpinner size="lg" />;

  return (
    <div>
      <PageHeader
        title="Failure Predictions"
        description="Run AI-powered failure risk analysis on sensor data"
        actions={
          <button onClick={handleRun} className="btn-primary" disabled={running} aria-label={running ? "Analyzing prediction" : "Run failure prediction"}>
            {running ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" aria-hidden="true" />
                Analyzing...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Zap className="w-4 h-4" aria-hidden="true" />
                Run Prediction
              </span>
            )}
          </button>
        }
      />

      {/* Prediction Result */}
      {result && (
        <div className="space-y-6 mb-8">
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
          >
            <div
              className={cn(
                "rounded-xl border-2 p-6",
                result.failure_prob >= 0.7
                  ? "border-accent-red/30 bg-accent-red/5"
                  : result.failure_prob >= 0.4
                  ? "border-accent-amber/30 bg-accent-amber/5"
                  : "border-accent-green/30 bg-accent-green/5"
              )}
              role="alert"
              aria-live="polite"
            >
              <div className="flex items-center gap-4 mb-4">
                {result.failure_prob >= 0.7 ? (
                  <AlertTriangle className="w-10 h-10 text-accent-red" aria-hidden="true" />
                ) : (
                  <CheckCircle className="w-10 h-10 text-accent-green" aria-hidden="true" />
                )}
                <div>
                  <h2
                    className="text-xl font-heading font-bold"
                    style={{ color: getFailureColor(result.failure_prob) }}
                  >
                    {result.prediction_class}
                  </h2>
                  <p className="text-text-muted text-sm">
                    Failure probability:{" "}
                    <span
                      className="font-semibold"
                      style={{ color: getFailureColor(result.failure_prob) }}
                    >
                      {(result.failure_prob * 100).toFixed(1)}%
                    </span>
                    {" "}· Confidence: {(result.confidence * 100).toFixed(0)}%
                  </p>
                </div>
              </div>

              {/* Top Features */}
              {result.top_features && result.top_features.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-text-muted mb-2">Top Contributing Factors</h4>
                  <div className="space-y-2">
                    {result.top_features.map((f: { feature: string; importance: number }, i: number) => (
                      <div key={i} className="flex items-center gap-3">
                        <span className="text-sm text-text-primary w-40 truncate">{f.feature}</span>
                        <div className="flex-1 h-2 rounded-full bg-base-elevated overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.min(Math.abs(f.importance) * 100, 100)}%` }}
                            transition={{ duration: 0.8, delay: i * 0.1 }}
                            className="h-full rounded-full"
                            style={{ backgroundColor: getFailureColor(result.failure_prob) }}
                          />
                        </div>
                        <span className="text-xs text-text-muted w-12 text-right">
                          {(f.importance * 100).toFixed(1)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>

          <NextStepCard
            title="Analysis Complete: Recommendations Ready"
            description="The AI model has assessed your vehicle's telemetry data. You can now view recommendations, prescribed actions, and anomalous sensor deviations."
            href={`/recommendations/${vehicleId}`}
            actionLabel="View Alerts & Recommendations"
            icon={Bell}
          />
        </div>
      )}

      {/* Dual Gauges */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-card p-6 flex items-center justify-center"
        >
          <div>
            <HealthGauge
              score={dashboard?.health_score ?? 0}
              band={dashboard?.health_band ?? "Health"}
              size="lg"
            />
            <p className="text-center text-sm text-text-muted mt-2">Vehicle Health</p>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="glass-card p-6 flex items-center justify-center"
        >
          {result ? (
            <div className="text-center">
              <div className="relative"
                role="progressbar"
                aria-valuenow={Math.round(result.failure_prob * 100)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Failure risk: ${(result.failure_prob * 100).toFixed(0)}%`}
              >
                <svg width={160} height={160} className="transform -rotate-90" aria-hidden="true">
                  <circle cx={80} cy={80} r={70} fill="none" stroke="rgba(30, 48, 71, 0.5)" strokeWidth={12} />
                  <motion.circle
                    cx={80} cy={80} r={70}
                    fill="none"
                    stroke={getFailureColor(result.failure_prob)}
                    strokeWidth={12}
                    strokeLinecap="round"
                    strokeDasharray={2 * Math.PI * 70}
                    initial={{ strokeDashoffset: 2 * Math.PI * 70 }}
                    animate={{ strokeDashoffset: 2 * Math.PI * 70 * (1 - result.failure_prob) }}
                    transition={{ duration: 1, ease: "easeOut" }}
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center" aria-hidden="true">
                  <div className="text-center">
                    <div className="font-heading font-bold text-3xl" style={{ color: getFailureColor(result.failure_prob) }}>
                      {(result.failure_prob * 100).toFixed(0)}%
                    </div>
                    <div className="text-[10px] text-text-muted tracking-wider uppercase">Failure Risk</div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center text-text-muted">
              <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-40" />
              <p className="text-sm">Run a prediction to see results</p>
            </div>
          )}
        </motion.div>
      </div>

      {/* Prediction History */}
      {predictions && predictions.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-card p-5"
        >
          <h3 className="font-heading font-semibold text-text-primary mb-4">Prediction History</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-label="Prediction history">
              <thead>
                <tr className="text-text-muted border-b border-border/30">
                  <th className="text-left py-2 px-3" scope="col">Date</th>
                  <th className="text-left py-2 px-3" scope="col">Prediction</th>
                  <th className="text-right py-2 px-3" scope="col">Failure Probability</th>
                  <th className="text-right py-2 px-3" scope="col">Health Score</th>
                </tr>
              </thead>
              <tbody>
                {predictions.map((p: { id: number; predicted_at: string | null; prediction: string; failure_prob: number | null; health_score: number | null }) => (
                  <tr key={p.id} className="border-b border-border/20 hover:bg-base-elevated/30 transition-colors">
                    <td className="py-2.5 px-3 text-text-muted">
                      {p.predicted_at ? new Date(p.predicted_at).toLocaleDateString() : "—"}
                    </td>
                    <td className="py-2.5 px-3">
                      <span style={{ color: getFailureColor(p.failure_prob ?? 0) }}>{p.prediction}</span>
                    </td>
                    <td className="py-2.5 px-3 text-right" style={{ color: getFailureColor(p.failure_prob ?? 0) }}>
                      {p.failure_prob != null ? `${(p.failure_prob * 100).toFixed(1)}%` : "—"}
                    </td>
                    <td className="py-2.5 px-3 text-right" style={{ color: getHealthColor(p.health_score ?? 0) }}>
                      {p.health_score != null ? p.health_score.toFixed(0) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}

      {!result && (!predictions || predictions.length === 0) && (
        <EmptyState
          icon={<Zap className="w-16 h-16" />}
          title="No predictions yet"
          description="Train a model first, then run a prediction to assess failure risk."
        />
      )}
    </div>
  );
}
