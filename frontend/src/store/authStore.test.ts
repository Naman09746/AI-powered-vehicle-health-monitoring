import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore } from "./authStore";

describe("authStore", () => {
  beforeEach(() => useAuthStore.setState({ token: null, user: null, selectedVehicleId: null }));

  it("starts unauthenticated", () => { const s = useAuthStore.getState(); expect(s.token).toBeNull(); expect(s.user).toBeNull(); });

  it("setAuth stores token and user", () => {
    useAuthStore.getState().setAuth("tok123", { id: 1, username: "admin", name: "Admin", role: "admin" });
    const s = useAuthStore.getState();
    expect(s.token).toBe("tok123");
    expect(s.user?.username).toBe("admin");
  });

  it("setSelectedVehicle updates selection", () => {
    useAuthStore.getState().setSelectedVehicle(42);
    expect(useAuthStore.getState().selectedVehicleId).toBe(42);
  });

  it("logout clears auth state", () => {
    useAuthStore.getState().setAuth("t", { id: 1, username: "u", name: null, role: "driver" });
    useAuthStore.getState().logout();
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
  });
});
