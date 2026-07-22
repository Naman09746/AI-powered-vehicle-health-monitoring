import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(value: number, decimals = 1): string {
  return value.toFixed(decimals);
}

export function formatTimestamp(ts: string | Date): string {
  const d = typeof ts === "string" ? new Date(ts) : ts;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function getFailureColor(prob: number): string {
  if (prob < 0.4) return "#10b981";
  if (prob < 0.7) return "#f59e0b";
  return "#ef4444";
}

export function getHealthColor(score: number): string {
  if (score >= 95) return "#10b981";
  if (score >= 80) return "#0ea5e9";
  if (score >= 60) return "#f59e0b";
  return "#ef4444";
}

export function getSeverityBadge(severity: string): string {
  switch (severity.toLowerCase()) {
    case "high": return "badge-high";
    case "medium": return "badge-medium";
    case "low": return "badge-low";
    default: return "badge";
  }
}
