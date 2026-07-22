"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import { motion } from "framer-motion";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return;
    setError("");
    setLoading(true);
    try {
      const { data } = await authApi.login(username, password);
      setAuth(data.token, {
        id: data.user_id,
        username: data.username,
        name: data.name ?? null,
        role: data.role,
      });
      router.replace("/fleet");
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Login failed. Check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  const isFormValid = username.trim() !== "" && password.trim() !== "";

  return (
    <div className="flex min-h-screen">
      {/* Left: Gradient background with telemetry visualization */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden bg-gradient-to-br from-[#0a1628] via-[#0f1924] to-[#080d14]">
        <div className="absolute inset-0 opacity-20">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent-sky/20 rounded-full blur-[120px]" />
          <div className="absolute bottom-1/4 right-1/4 w-64 h-64 bg-accent-green/10 rounded-full blur-[100px]" />
        </div>
        <div className="relative z-10 flex flex-col justify-center px-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="w-14 h-14 rounded-xl bg-accent-sky/10 border border-accent-sky/20 flex items-center justify-center mb-8">
              <span className="text-accent-sky font-heading font-bold text-xl">VH</span>
            </div>
            <h1 className="text-4xl font-heading font-bold text-text-primary mb-4">
              Vehicle Health Monitor
            </h1>
            <p className="text-text-muted text-lg leading-relaxed max-w-md">
              AI-powered predictive maintenance platform. Track sensor telemetry,
              train ML models, and predict failures before they happen.
            </p>
            <div className="mt-12 grid grid-cols-3 gap-4">
              {["Real-time telemetry", "ML predictions", "Fleet analytics"].map((feat) => (
                <div
                  key={feat}
                  className="px-4 py-3 rounded-lg bg-base-surface/50 border border-border/30 text-sm text-text-muted"
                >
                  {feat}
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>

      {/* Right: Login form */}
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
            <span className="font-heading font-semibold text-text-primary">
              Vehicle Health
            </span>
          </div>

          <h2 className="text-2xl font-heading font-bold text-text-primary mb-1">
            Welcome back
          </h2>
          <p className="text-text-muted text-sm mb-8">
            Sign in to access your fleet dashboard
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-3 rounded-lg bg-accent-red/10 border border-accent-red/20 text-accent-red text-sm"
              >
                {error}
              </motion.div>
            )}

            <div>
              <label htmlFor="username" className="block text-sm font-medium text-text-muted mb-1.5">
                Username
              </label>
              <input
                id="username"
                type="text"
                className="input-field"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-text-muted mb-1.5">
                Password
              </label>
              <input
                id="password"
                type="password"
                className="input-field"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <button type="submit" className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed" disabled={loading || !isFormValid}>
              {loading ? "Signing in..." : "Sign in"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-text-muted">
            Don't have an account?{" "}
            <Link href="/register" className="text-accent-sky hover:underline">
              Create one
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
