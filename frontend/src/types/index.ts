export interface User {
  id: number;
  username: string;
  name: string | null;
  email?: string | null;
  role: string;
}

export interface Vehicle {
  id: number;
  vehicle_id_display: string;
  model: string | null;
  manufacturing_year: number | null;
  engine_type: string | null;
  mileage: number | null;
  last_service_date: string | null;
  created_at: string | null;
}

export interface SensorReading {
  id: number;
  timestamp: string | null;
  engine_temp: number | null;
  oil_pressure: number | null;
  coolant_temp: number | null;
  engine_rpm: number | null;
  vibration: number | null;
  fuel_consumption: number | null;
  battery_voltage: number | null;
  tire_pressure: number | null;
  speed: number | null;
  engine_load: number | null;
}

export interface DashboardData {
  vehicle: Vehicle;
  recent_readings: SensorReading[];
  health_score: number | null;
  health_band: string | null;
  active_alerts: number;
  total_readings: number;
}

export interface TrainedModel {
  id: number;
  model_name: string;
  model_version: string | null;
  accuracy: number | null;
  f1: number | null;
  roc_auc: number | null;
  is_champion: boolean;
  trained_at: string | null;
}

export interface PredictionResult {
  prediction_id: number;
  prediction_class: string;
  failure_prob: number;
  confidence: number;
  top_features: { feature: string; importance: number }[];
  prediction_icon?: string;
  prediction_color?: string;
}

export interface Alert {
  id: number;
  alert_type: string;
  severity: string;
  message: string;
  is_dismissed: boolean;
  created_at: string | null;
}

export interface FleetOverview {
  vehicle_count: number;
  avg_health_score: number | null;
  healthy_count: number;
  at_risk_count: number;
  critical_count: number;
  total_active_alerts: number;
}

export interface Recommendation {
  sensor: string;
  condition: string;
  action: string;
  description: string;
  priority: string;
  current_value: number | null;
  normal_range: string | null;
}

export interface UploadResult {
  upload_id: number;
  row_count_raw: number;
  row_count_clean: number;
  log_entries: string[];
  preview: Record<string, unknown>[];
}

export interface TrainingStatus {
  job_id: string;
  status: "pending" | "started" | "running" | "complete" | "failed";
  result?: unknown;
}

export interface MaintenanceRecord {
  id: number;
  service_date: string;
  service_type: string;
  parts_replaced: string | null;
  cost: number | null;
  notes: string | null;
  created_at: string | null;
}
