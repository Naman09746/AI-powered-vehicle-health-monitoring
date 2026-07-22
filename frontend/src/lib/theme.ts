/** Theme management for dark/light/system toggle. */

export type Theme = "dark" | "light" | "system";
const KEY = "vh-theme";

export function getStoredTheme(): Theme {
  if (typeof window === "undefined") return "system";
  return (localStorage.getItem(KEY) as Theme) ?? "system";
}

export function setTheme(theme: Theme): void {
  localStorage.setItem(KEY, theme);
  applyTheme(theme);
}

export function toggleTheme(): Theme {
  const current = getStoredTheme();
  const next = current === "dark" ? "light" : current === "light" ? "system" : "dark";
  setTheme(next);
  return next;
}

export function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") return;
  const isDark = theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", isDark);
  document.documentElement.classList.toggle("light", !isDark);
  document.querySelector("meta[name='theme-color']")?.setAttribute("content", isDark ? "#0a1628" : "#f8fafc");
}
