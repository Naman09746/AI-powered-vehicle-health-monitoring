/**
 * Zod schemas for API response validation.
 * Import these to validate API responses at runtime (FE-04).
 *
 * Usage:
 *   import { vehicleSchema, type Vehicle } from "@/lib/validation";
 *   const vehicle = vehicleSchema.parse(response.data);
 */

import { z } from "zod";

// ── Auth ──

export const loginResponseSchema = z.object({
  token: z.string(),
  user_id: z.number(),
  username: z.string(),
  role: z.string(),
  name: z.string().nullable(),
});

export const registerResponseSchema = z.object({
  status: z.string(),
  detail: z.string(),
});

// ── Vehicles ──

export const vehicleSchema = z.object({
  id: z.number(),
  vehicle_id_display: z.string(),
  model: z.string().nullable(),
  manufacturing_year: z.number().nullable(),
  engine_type: z.string().nullable(),
  mileage: z.number().nullable(),
  last_service_date: z.string().nullable(),
  created_at: z.string().nullable(),
});

export const vehicleListSchema = z.array(vehicleSchema);

// ── Sensor Readings ──

export const sensorReadingSchema = z.object({
  id: z.number(),
  timestamp: z.string().nullable(),
  engine_temp: z.number().nullable(),
  oil_pressure: z.number().nullable(),
  coolant_temp: z.number().nullable(),
  engine_rpm: z.number().nullable(),
  vibration: z.number().nullable(),
  fuel_consumption: z.number().nullable(),
  battery_voltage: z.number().nullable(),
  tire_pressure: z.number().nullable(),
  speed: z.number().nullable(),
  engine_load: z.number().nullable(),
});

// ── Dashboard ──

export const dashboardDataSchema = z.object({
  vehicle: vehicleSchema,
  recent_readings: z.array(sensorReadingSchema),
  health_score: z.number().nullable(),
  health_band: z.string().nullable(),
  active_alerts: z.number(),
  total_readings: z.number(),
});

// ── ML Models ──

export const trainedModelSchema = z.object({
  id: z.number(),
  model_name: z.string(),
  model_version: z.string().nullable(),
  accuracy: z.number().nullable(),
  f1: z.number().nullable(),
  roc_auc: z.number().nullable(),
  is_champion: z.boolean(),
  trained_at: z.string().nullable(),
});

export const trainedModelListSchema = z.array(trainedModelSchema);

// ── Predictions ──

export const predictionResultSchema = z.object({
  prediction_id: z.number(),
  prediction_class: z.string(),
  failure_prob: z.number(),
  confidence: z.number(),
  top_features: z.array(
    z.object({
      feature: z.string(),
      importance: z.number(),
    })
  ),
});

// ── Alerts ──

export const alertSchema = z.object({
  id: z.number(),
  alert_type: z.string(),
  severity: z.string(),
  message: z.string(),
  is_dismissed: z.boolean(),
  created_at: z.string().nullable(),
});

export const alertListSchema = z.array(alertSchema);

// ── Fleet Overview ──

export const fleetOverviewSchema = z.object({
  vehicle_count: z.number(),
  avg_health_score: z.number().nullable(),
  healthy_count: z.number(),
  at_risk_count: z.number(),
  critical_count: z.number(),
  total_active_alerts: z.number(),
});

// ── Inferred types ──

export type LoginResponse = z.infer<typeof loginResponseSchema>;
export type Vehicle = z.infer<typeof vehicleSchema>;
export type SensorReading = z.infer<typeof sensorReadingSchema>;
export type DashboardData = z.infer<typeof dashboardDataSchema>;
export type TrainedModel = z.infer<typeof trainedModelSchema>;
export type PredictionResult = z.infer<typeof predictionResultSchema>;
export type Alert = z.infer<typeof alertSchema>;
export type FleetOverview = z.infer<typeof fleetOverviewSchema>;
