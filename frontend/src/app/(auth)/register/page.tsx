"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import { motion } from "framer-motion";
import { Activity } from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [form, setForm] = useState({ username: "", password: "", confirmPassword: "", name: "", email: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (form.password.length < 6) { setError("Password must be at least 6 characters."); return; }
    if (form.password !== form.confirmPassword) { setError("Passwords do not match."); return; }
    setLoading(true);
    try {
      // Register then auto-login so user lands in onboarding immediately
      await authApi.register({ username: form.username, password: form.password, name: form.name || undefined, email: form.email || undefined });
      const { data } = await authApi.login(form.username, form.password);
      setAuth(data.token, { id: data.user_id, username: data.username, name: data.name ?? null, role: data.role });
      router.replace("/onboarding");
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Registration failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      {/* Left branding panel */}
      <div className="hidden lg:flex lg:w-5/12 relative overflow-hidden bg-gradient-to-br from-[#0a1628] via-[#0f1924] to-[#080d14]">
        <div className="absolute inset-0 opacity-20">
          <div className="absolute top-1/3 left-1/4 w-96 h-96 bg-accent-sky/20 rounded-full blur-[120px]" />
          <div className="absolute bottom-1/4 right-1/4 w-64 h-64 bg-accent-green/10 rounded-full blur-[100px]" />
        </div>
        <div className="relative z-10 flex flex-col justify-center px-12">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <div className="w-14 h-14 rounded-xl bg-accent-sky/10 border border-accent-sky/20 flex items-center justify-center mb-8">
              <Activity className="w-7 h-7 text-accent-sky" />
            </div>
            <h1 className="text-3xl font-heading font-bold text-text-primary mb-3">
              Vehicle Health Monitor
            </h1>
            <p className="text-text-muted leading-relaxed max-w-sm text-sm">
              Create your free account to start monitoring OBD-II telemetry, tracking health scores, and predicting failures with AI.
            </p>
            <div className="mt-10 space-y-3 text-sm text-text-muted">
              {["Real-time sensor telemetry", "AI failure prediction", "Driver behavior scoring", "Maintenance forecasting"].map((f) => (
                <div key={f} className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent-sky" />
                  {f}
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>

      {/* Right: Registration form */}
      <div className="flex-1 flex items-center justify-center px-6 bg-base">
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="w-full max-w-sm"
        >
          <div className="lg:hidden flex items-center gap-3 mb-10">
            <div className="w-10 h-10 rounded-lg bg-accent-sky/10 border border-accent-sky/20 flex items-center justify-center">
              <span className="text-accent-sky font-heading font-semibold">VH</span>
            </div>
            <span className="font-heading font-semibold text-text-primary">Vehicle Health</span>
          </div>

          <h2 className="text-2xl font-heading font-bold text-text-primary mb-1">Create your account</h2>
          <p className="text-text-muted text-sm mb-8">Set up your fleet monitoring workspace in seconds.</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }}
                className="p-3 rounded-lg bg-accent-red/10 border border-accent-red/20 text-accent-red text-sm">
                {error}
              </motion.div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="reg-username" className="block text-xs font-medium text-text-muted mb-1.5">Username *</label>
                <input id="reg-username" className="input-field" placeholder="fleet_admin" value={form.username} onChange={handleChange("username")} required autoComplete="username" />
              </div>
              <div>
                <label htmlFor="reg-name" className="block text-xs font-medium text-text-muted mb-1.5">Full Name</label>
                <input id="reg-name" className="input-field" placeholder="Jane Smith" value={form.name} onChange={handleChange("name")} autoComplete="name" />
              </div>
            </div>

            <div>
              <label htmlFor="reg-email" className="block text-xs font-medium text-text-muted mb-1.5">Email Address</label>
              <input id="reg-email" type="email" className="input-field" placeholder="you@company.com" value={form.email} onChange={handleChange("email")} autoComplete="email" />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="reg-password" className="block text-xs font-medium text-text-muted mb-1.5">Password *</label>
                <input id="reg-password" type="password" className="input-field" placeholder="Min 6 chars" value={form.password} onChange={handleChange("password")} required autoComplete="new-password" minLength={6} />
              </div>
              <div>
                <label htmlFor="reg-confirm" className="block text-xs font-medium text-text-muted mb-1.5">Confirm *</label>
                <input id="reg-confirm" type="password" className="input-field" placeholder="Repeat" value={form.confirmPassword} onChange={handleChange("confirmPassword")} required autoComplete="new-password" minLength={6} />
              </div>
            </div>

            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? "Creating account..." : "Create account & continue"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-text-muted">
            Already have an account?{" "}
            <Link href="/login" className="text-accent-sky hover:underline">Sign in</Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
