import { describe, it, expect } from "vitest";
import { vehicleSchema, loginResponseSchema, dashboardDataSchema, fleetOverviewSchema } from "./validation";

describe("vehicleSchema", () => {
  it("validates a correct vehicle", () => {
    const result = vehicleSchema.safeParse({ id: 1, vehicle_id_display: "VH-001", model: "Tesla", manufacturing_year: 2025, engine_type: "Electric", mileage: 5000, last_service_date: null, created_at: null });
    expect(result.success).toBe(true);
  });
  it("rejects missing required fields", () => { expect(vehicleSchema.safeParse({}).success).toBe(false); });
});

describe("loginResponseSchema", () => {
  it("validates a correct login response", () => {
    const result = loginResponseSchema.safeParse({ token: "abc", user_id: 1, username: "admin", role: "admin", name: "Admin" });
    expect(result.success).toBe(true);
  });
  it("allows null name", () => { expect(loginResponseSchema.safeParse({ token: "a", user_id: 1, username: "u", role: "driver", name: null }).success).toBe(true); });
});

describe("fleetOverviewSchema", () => {
  it("validates fleet overview", () => {
    const result = fleetOverviewSchema.safeParse({ vehicle_count: 5, avg_health_score: 85, healthy_count: 3, at_risk_count: 2, critical_count: 0, total_active_alerts: 1 });
    expect(result.success).toBe(true);
  });
});

describe("dashboardDataSchema", () => {
  it("validates dashboard data", () => {
    const result = dashboardDataSchema.safeParse({
      vehicle: { id: 1, vehicle_id_display: "VH-001", model: null, manufacturing_year: null, engine_type: null, mileage: null, last_service_date: null, created_at: null },
      recent_readings: [],
      health_score: 92,
      health_band: "Good",
      active_alerts: 0,
      total_readings: 100,
    });
    expect(result.success).toBe(true);
  });
});
