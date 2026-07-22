"use client";

import { useAuthStore } from "@/store/authStore";
import { useRouter, usePathname } from "next/navigation";
import { LogOut, User, Sun, Moon, Menu } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { vehicleApi } from "@/lib/api";
import { useVehicles } from "@/hooks/useVehicles";
import { getStoredTheme, setTheme } from "@/lib/theme";
import { useUIStore } from "@/store/uiStore";
import { useState, useEffect } from "react";

export function Topbar() {
  const router = useRouter();
  const pathname = usePathname();
  const { user, selectedVehicleId, setSelectedVehicle, logout } = useAuthStore();
  const { data: vehicles } = useVehicles();
  const [theme, setThemeState] = useState(getStoredTheme());
  const toggleMobileSidebar = useUIStore((s) => s.toggleMobileSidebar);

  // Sync URL vehicleId parameter back to the auth store
  useEffect(() => {
    const parts = pathname.split("/");
    if (parts.length >= 3 && /^\d+$/.test(parts[2])) {
      const urlVehicleId = Number(parts[2]);
      if (urlVehicleId !== selectedVehicleId) {
        setSelectedVehicle(urlVehicleId);
      }
    }
  }, [pathname, selectedVehicleId, setSelectedVehicle]);

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const handleVehicleChange = (id: number) => {
    setSelectedVehicle(id);
    const parts = pathname.split("/");
    if (parts.length >= 3 && /^\d+$/.test(parts[2])) {
      parts[2] = String(id);
      router.push(parts.join("/"));
    } else {
      router.push(`/dashboard/${id}`);
    }
  };

  return (
    <header className="h-16 border-b border-border/30 bg-base-surface/60 backdrop-blur-xl flex items-center justify-between px-6 lg:px-8 sticky top-0 z-20" role="banner">
      <div className="flex items-center gap-4">
        <button
          onClick={toggleMobileSidebar}
          className="btn-ghost p-2 lg:hidden"
          aria-label="Toggle mobile menu"
        >
          <Menu className="w-5 h-5 text-text-primary" />
        </button>
        <div className="hidden lg:block">
          {vehicles && vehicles.length > 0 && (
            <select
              className="input-field w-64"
              value={selectedVehicleId ?? ""}
              onChange={(e) => handleVehicleChange(Number(e.target.value))}
              aria-label="Select a vehicle to view"
            >
              <option value="" disabled>
                Select a vehicle...
              </option>
              {vehicles.map((v: { id: number; vehicle_id_display: string; model: string | null }) => (
                <option key={v.id} value={v.id}>
                  {v.vehicle_id_display} — {v.model ?? "Unknown"}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-accent-sky/10 border border-accent-sky/20 flex items-center justify-center" aria-hidden="true">
            <User className="w-4 h-4 text-accent-sky" />
          </div>
          <div className="hidden sm:block">
            <div className="text-sm text-text-primary font-medium">{user?.name ?? user?.username}</div>
            <div className="text-[11px] text-text-muted capitalize">{user?.role}</div>
          </div>
        </div>
        <button
          onClick={() => { const t = theme === "dark" ? "light" : theme === "light" ? "system" : "dark"; setTheme(t); setThemeState(t); }}
          className="btn-ghost p-2"
          aria-label={`Switch to ${theme === "dark" ? "light" : "system"} theme`}
        >
          {theme === "dark" ? <Sun className="w-4 h-4" aria-hidden="true" /> : <Moon className="w-4 h-4" aria-hidden="true" />}
        </button>
        <button
          onClick={handleLogout}
          className="btn-ghost p-2"
          aria-label="Log out"
        >
          <LogOut className="w-4 h-4" aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}
