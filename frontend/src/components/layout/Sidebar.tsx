"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { useVehicles } from "@/hooks/useVehicles";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/store/uiStore";
import {
  LayoutDashboard,
  Upload,
  Brain,
  BarChart3,
  Bell,
  Truck,
  History,
  FileText,
  Activity,
  X,
} from "lucide-react";

export function Sidebar() {
  const pathname = usePathname();
  const selectedVehicleId = useAuthStore((s) => s.selectedVehicleId);
  const setSelectedVehicle = useAuthStore((s) => s.setSelectedVehicle);
  const { data: vehicles } = useVehicles();
  const mobileSidebarOpen = useUIStore((s) => s.mobileSidebarOpen);
  const setMobileSidebarOpen = useUIStore((s) => s.setMobileSidebarOpen);

  // Get effective vehicle ID: selected one, or first available
  const vehicleList = Array.isArray(vehicles) ? vehicles : [];
  const defaultVehicleId = selectedVehicleId ?? vehicleList[0]?.id ?? null;

  const v = (path: string) => {
    const vid = defaultVehicleId;
    if (!vid) return "/fleet";
    if (path === "/dashboard") return `/dashboard/${vid}`;
    if (path === "/upload") return `/upload/${vid}`;
    if (path === "/training") return `/training/${vid}`;
    if (path === "/predictions") return `/predictions/${vid}`;
    if (path === "/recommendations") return `/recommendations/${vid}`;
    if (path === "/history") return `/history/${vid}`;
    if (path === "/reports") return `/reports/${vid}`;
    return path;
  };

  const navItems = [
    { href: "/fleet", label: "Fleet", icon: Truck },
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/upload", label: "Upload", icon: Upload },
    { href: "/training", label: "Training", icon: Brain },
    { href: "/predictions", label: "Predictions", icon: BarChart3 },
    { href: "/recommendations", label: "Alerts", icon: Bell },
    { href: "/history", label: "History", icon: History },
    { href: "/reports", label: "Reports", icon: FileText },
  ];

  const isActive = (href: string) => pathname.startsWith(href) || pathname === href;

  return (
    <>
      {/* Mobile backdrop */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setMobileSidebarOpen(false)}
        />
      )}

      <aside
        className={cn(
          "flex flex-col w-60 h-screen fixed left-0 top-0 bg-base-surface/90 backdrop-blur-xl border-r border-border/50 z-45 transition-transform duration-300 lg:translate-x-0 z-50",
          mobileSidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
        aria-label="Main navigation"
      >
        <div className="flex items-center justify-between px-5 h-16 border-b border-border/30 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-accent-sky/10 border border-accent-sky/20 flex items-center justify-center" aria-hidden="true">
              <span className="text-accent-sky font-heading font-bold text-sm">VH</span>
            </div>
            <div>
              <div className="font-heading font-semibold text-sm text-text-primary">Vehicle Health</div>
              <div className="text-[10px] text-text-muted tracking-widest uppercase">Monitor</div>
            </div>
          </div>
          <button
            onClick={() => setMobileSidebarOpen(false)}
            className="btn-ghost p-1 lg:hidden"
            aria-label="Close menu"
          >
            <X className="w-4 h-4 text-text-primary" />
          </button>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto" aria-label="Sidebar navigation">
          {navItems.map((item) => {
            const active = isActive(item.href);
            const resolvedHref = v(item.href);
            const isDisabled = !defaultVehicleId && item.href !== "/fleet";

            if (isDisabled) {
              return (
                <div
                  key={item.href}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-text-muted/40 cursor-not-allowed text-sm font-medium select-none"
                  title="Please add a vehicle first"
                  aria-disabled="true"
                >
                  <item.icon className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
                  <span>{item.label}</span>
                </div>
              );
            }

            return (
              <Link key={item.href} href={resolvedHref}
                className={cn("nav-link", active && "nav-link-active")}
                aria-current={active ? "page" : undefined}
                onClick={() => {
                  setMobileSidebarOpen(false);
                  // Auto-select first vehicle if none selected and clicking a vehicle page
                  if (!selectedVehicleId && vehicleList[0] && item.href !== "/fleet") {
                    setSelectedVehicle(vehicleList[0].id);
                  }
                }}
              >
                <item.icon className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="px-5 py-4 border-t border-border/30 flex-shrink-0">
          <div className="text-[10px] text-text-muted/50 tracking-wider">v2.0.0 • AI-Powered</div>
        </div>
      </aside>
    </>
  );
}
