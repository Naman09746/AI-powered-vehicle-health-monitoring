"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { motion } from "framer-motion";
import { Mail, ArrowLeft, CheckCircle2 } from "lucide-react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setError("");
    setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSubmitted(true);
    } catch {
      setError("Failed to request password reset. Try again later.");
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

        {submitted ? (
          <div className="text-center py-4">
            <div className="w-12 h-12 rounded-full bg-accent-green/10 text-accent-green flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold font-heading mb-2">Check your inbox</h2>
            <p className="text-text-muted text-sm mb-6">
              If an account with <strong>{email}</strong> exists, we've sent a password reset link.
            </p>
            <Link href="/login" className="btn-primary w-full inline-block">
              Return to Login
            </Link>
          </div>
        ) : (
          <div>
            <div className="w-10 h-10 rounded-xl bg-accent-sky/10 text-accent-sky border border-accent-sky/20 flex items-center justify-center mb-4">
              <Mail className="w-5 h-5" />
            </div>
            <h2 className="text-2xl font-bold font-heading mb-1">Reset your password</h2>
            <p className="text-text-muted text-sm mb-6">
              Enter your registered email address and we'll send you a password reset link.
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              {error && <div className="p-3 rounded-lg bg-accent-red/10 text-accent-red text-sm">{error}</div>}
              <div>
                <label htmlFor="resEmail" className="block text-xs font-medium text-text-muted mb-1">
                  Email Address
                </label>
                <input
                  id="resEmail"
                  type="email"
                  className="input-field"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoFocus
                />
              </div>
              <button type="submit" disabled={loading || !email.trim()} className="btn-primary w-full">
                {loading ? "Sending link..." : "Send Reset Link"}
              </button>
            </form>
          </div>
        )}
      </motion.div>
    </div>
  );
}
