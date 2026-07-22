"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { authApi } from "@/lib/api";
import { motion } from "framer-motion";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    username: "",
    password: "",
    confirmPassword: "",
    name: "",
    email: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (form.password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      await authApi.register({
        username: form.username,
        password: form.password,
        name: form.name || undefined,
        email: form.email || undefined,
      });
      router.push("/login");
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Registration failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-6 bg-base">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md"
      >
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-lg bg-accent-sky/10 border border-accent-sky/20 flex items-center justify-center">
            <span className="text-accent-sky font-heading font-bold">VH</span>
          </div>
          <span className="font-heading font-semibold text-text-primary">
            Vehicle Health Monitor
          </span>
        </div>

        <h2 className="text-2xl font-heading font-bold text-text-primary mb-1">
          Create your account
        </h2>
        <p className="text-text-muted text-sm mb-8">
          Set up your fleet monitoring workspace
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

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="reg-username" className="block text-sm font-medium text-text-muted mb-1.5">Username *</label>
              <input id="reg-username" className="input-field" placeholder="Choose a username" value={form.username} onChange={handleChange("username")} required autoComplete="username" />
            </div>
            <div>
              <label htmlFor="reg-name" className="block text-sm font-medium text-text-muted mb-1.5">Full name</label>
              <input id="reg-name" className="input-field" placeholder="Your name" value={form.name} onChange={handleChange("name")} autoComplete="name" />
            </div>
          </div>

          <div>
            <label htmlFor="reg-email" className="block text-sm font-medium text-text-muted mb-1.5">Email</label>
            <input id="reg-email" type="email" className="input-field" placeholder="you@example.com" value={form.email} onChange={handleChange("email")} autoComplete="email" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="reg-password" className="block text-sm font-medium text-text-muted mb-1.5">Password *</label>
              <input id="reg-password" type="password" className="input-field" placeholder="Min 6 characters" value={form.password} onChange={handleChange("password")} required autoComplete="new-password" minLength={6} />
            </div>
            <div>
              <label htmlFor="reg-confirm" className="block text-sm font-medium text-text-muted mb-1.5">Confirm *</label>
              <input id="reg-confirm" type="password" className="input-field" placeholder="Repeat password" value={form.confirmPassword} onChange={handleChange("confirmPassword")} required autoComplete="new-password" minLength={6} />
            </div>
          </div>

          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-text-muted">
          Already have an account?{" "}
          <Link href="/login" className="text-accent-sky hover:underline">Sign in</Link>
        </p>
      </motion.div>
    </div>
  );
}
