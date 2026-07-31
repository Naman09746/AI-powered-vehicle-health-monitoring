"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { motion } from "framer-motion";
import { KeyRound, ArrowLeft, CheckCircle2, Eye, EyeOff } from "lucide-react";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 6) { setError("Password must be at least 6 characters."); return; }
    if (password !== confirm) { setError("Passwords do not match."); return; }
    if (!token) { setError("Invalid or missing reset token."); return; }

    setLoading(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: password });
      setDone(true);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Password reset failed. The link may have expired.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-base items-center justify-center px-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-md glass-card p-8">
        <Link href="/login" className="inline-flex items-center gap-2 text-xs text-text-muted hover:text-text-primary mb-6 transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back to Sign In
        </Link>

        {done ? (
          <div className="text-center py-4">
            <div className="w-12 h-12 rounded-full bg-accent-green/10 text-accent-green flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold font-heading mb-2">Password Updated</h2>
            <p className="text-text-muted text-sm mb-6">Your password has been reset. Sign in with your new password.</p>
            <button onClick={() => router.replace("/login")} className="btn-primary w-full">
              Sign In Now
            </button>
          </div>
        ) : (
          <div>
            <div className="w-10 h-10 rounded-xl bg-accent-sky/10 text-accent-sky border border-accent-sky/20 flex items-center justify-center mb-4">
              <KeyRound className="w-5 h-5" />
            </div>
            <h2 className="text-2xl font-bold font-heading mb-1">Set a new password</h2>
            <p className="text-text-muted text-sm mb-6">
              {!token ? "This reset link is invalid or expired." : "Choose a strong password for your account."}
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              {error && <div className="p-3 rounded-lg bg-accent-red/10 text-accent-red text-sm border border-accent-red/20">{error}</div>}

              <div>
                <label htmlFor="newPw" className="block text-xs font-medium text-text-muted mb-1.5">New Password</label>
                <div className="relative">
                  <input
                    id="newPw"
                    type={showPw ? "text" : "password"}
                    className="input-field pr-10"
                    placeholder="Min 6 characters"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={6}
                    autoFocus
                  />
                  <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary">
                    {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label htmlFor="confirmPw" className="block text-xs font-medium text-text-muted mb-1.5">Confirm Password</label>
                <input
                  id="confirmPw"
                  type="password"
                  className="input-field"
                  placeholder="Repeat password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  minLength={6}
                />
              </div>

              <button type="submit" disabled={loading || !token || !password || !confirm} className="btn-primary w-full">
                {loading ? "Saving..." : "Reset Password"}
              </button>
            </form>
          </div>
        )}
      </motion.div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-base flex items-center justify-center"><div className="w-8 h-8 border-2 border-accent-sky border-t-transparent rounded-full animate-spin" /></div>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
