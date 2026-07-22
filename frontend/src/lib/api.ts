import axios from "axios";
import { useAuthStore } from "@/store/authStore";

const rawApiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
export const API_BASE_URL = rawApiUrl.replace(/\/+$/, "");

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 60_000,
});

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

// ── Auth ──

export const authApi = {
  login: (username: string, password: string) =>
    api.post("/auth/login", { username, password }),
  register: (data: { username: string; password: string; name?: string; email?: string }) =>
    api.post("/auth/register", data),
  me: () => api.get("/auth/me"),
};

// ── Vehicles ──

export const vehicleApi = {
  list: () => api.get("/vehicles"),
  create: (data: { vehicle_id_display: string; model?: string; manufacturing_year?: number; engine_type?: string }) =>
    api.post("/vehicles", data),
  get: (id: number) => api.get(`/vehicles/${id}`),
  delete: (id: number) => api.delete(`/vehicles/${id}`),
};

// ── Dashboard ──

export const dashboardApi = {
  get: (vehicleId: number) => api.get(`/dashboard/${vehicleId}`),
};

// ── Uploads ──

export const uploadApi = {
  upload: (vehicleId: number, file: File, onProgress?: (pct: number) => void) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post(`/uploads/${vehicleId}`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
      },
    });
  },
  history: (vehicleId: number) => api.get(`/uploads/${vehicleId}`),
  sampleCsv: () => api.get("/uploads/sample-csv", { responseType: "blob" }),
  delete: (uploadId: number) => api.delete(`/uploads/${uploadId}`),
};

// ── ML ──

export const mlApi = {
  train: (vehicleId: number, tuningMode = "quick") =>
    api.post(`/ml/train/${vehicleId}?tuning_mode=${tuningMode}`),
  trainingStatus: (jobId: string) => api.get(`/ml/train/status/${jobId}`),
  models: (vehicleId?: number) =>
    api.get(vehicleId ? `/ml/models/${vehicleId}` : "/ml/models"),
  promoteModel: (modelId: number, vehicleId: number) =>
    api.post(`/ml/models/${modelId}/promote?vehicle_id=${vehicleId}`),
  deleteModel: (modelId: number) => api.delete(`/ml/models/${modelId}`),
};

// ── Predictions ──

export const predictionApi = {
  run: (vehicleId: number) => api.post("/predictions/run", {}, { params: { vehicle_id: vehicleId } }),
  list: (vehicleId: number) => api.get("/predictions", { params: { vehicle_id: vehicleId } }),
};

// ── Alerts ──

export const alertApi = {
  list: (vehicleId: number, activeOnly = true) =>
    api.get("/alerts", { params: { vehicle_id: vehicleId, active_only: activeOnly } }),
  dismiss: (alertId: number) => api.patch(`/alerts/${alertId}/dismiss`),
  acknowledge: (alertId: number) => api.patch(`/alerts/${alertId}/acknowledge`),
};

// ── Recommendations ──

export const recommendationApi = {
  list: (vehicleId: number) => api.get(`/recommendations/${vehicleId}`),
};

// ── Fleet ──

export const fleetApi = {
  overview: () => api.get("/fleet/overview"),
};

// ── History ──

export const historyApi = {
  list: (vehicleId: number) => api.get(`/history/${vehicleId}`),
  create: (vehicleId: number, data: Record<string, unknown>) => api.post(`/history/${vehicleId}`, data),
  update: (vehicleId: number, recordId: number, data: Record<string, unknown>) =>
    api.put(`/history/${vehicleId}/${recordId}`, data),
  delete: (vehicleId: number, recordId: number) =>
    api.delete(`/history/${vehicleId}/${recordId}`),
};

// ── Simulator ──

export const simulatorApi = {
  start: (vehicleId: number, profile = "healthy", interval = 3) =>
    api.post(`/simulator/start/${vehicleId}`, null, { params: { profile, interval } }),
  stop: (vehicleId: number) =>
    api.post(`/simulator/stop/${vehicleId}`),
  status: (vehicleId: number) =>
    api.get(`/simulator/status/${vehicleId}`),
};

// ── Reports ──

export const reportApi = {
  pdf: async (vehicleId: number) => {
    const response = await api.get(`/reports/${vehicleId}/pdf`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(new Blob([response.data], { type: "application/pdf" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `vehicle_report_${vehicleId}.pdf`;
    link.click();
    URL.revokeObjectURL(url);
  },
};
