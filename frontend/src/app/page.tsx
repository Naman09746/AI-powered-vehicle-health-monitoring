"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/store/authStore";
import {
  Activity,
  Brain,
  ShieldCheck,
  Zap,
  LineChart,
  BellRing,
  ArrowRight,
  Truck,
  CheckCircle2,
  Lock,
} from "lucide-react";

export default function Home() {
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  return (
    <div className="min-h-screen bg-base text-text-primary flex flex-col font-body selection:bg-accent-sky/20 selection:text-text-primary">
      {/* Top Banner if logged in */}
      {isClient && token && (
        <div className="bg-accent-sky/10 border-b border-accent-sky/20 py-2.5 px-4 text-center text-xs sm:text-sm font-medium text-accent-sky flex items-center justify-center gap-2">
          <span>Welcome back, {user?.name || user?.username || "User"}! You are currently signed in.</span>
          <Link href="/fleet" className="underline font-bold hover:text-white transition-colors flex items-center gap-1">
            Go to Dashboard <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      )}

      {/* Navigation Bar */}
      <header className="h-20 border-b border-border/40 bg-base-surface/80 backdrop-blur-xl sticky top-0 z-50 px-6 lg:px-12 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-accent-sky/10 border border-accent-sky/30 flex items-center justify-center shadow-[0_0_15px_rgba(14,165,233,0.15)]">
            <Activity className="w-5 h-5 text-accent-sky" />
          </div>
          <div>
            <span className="font-heading font-bold text-lg text-text-primary tracking-tight">Vehicle Health</span>
            <span className="text-[10px] text-accent-sky block font-mono tracking-widest uppercase -mt-1">AI Monitor v3.0</span>
          </div>
        </div>

        <nav className="flex items-center gap-4">
          {isClient && token ? (
            <Link href="/fleet" className="btn-primary flex items-center gap-2">
              <span>Go to Fleet</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          ) : (
            <>
              <Link href="/login" className="px-4 py-2 text-sm font-medium text-text-muted hover:text-text-primary transition-colors">
                Sign In
              </Link>
              <Link href="/register" className="btn-primary flex items-center gap-2">
                <span>Get Started Free</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </>
          )}
        </nav>
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section className="relative py-20 lg:py-32 px-6 lg:px-12 max-w-7xl mx-auto text-center overflow-hidden">
          <div className="absolute top-12 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-accent-sky/10 blur-[120px] rounded-full pointer-events-none -z-10" />

          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-accent-sky/10 border border-accent-sky/20 text-accent-sky text-xs font-semibold uppercase tracking-wider mb-8">
            <Zap className="w-3.5 h-3.5" /> Next-Gen Predictive Maintenance
          </div>

          <h1 className="font-heading text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-text-primary max-w-4xl mx-auto leading-[1.15]">
            AI-Powered Real-Time <br />
            <span className="bg-gradient-to-r from-accent-sky via-sky-300 to-indigo-400 bg-clip-text text-transparent">
              Vehicle Health Monitoring
            </span>
          </h1>

          <p className="mt-6 text-lg sm:text-xl text-text-muted max-w-2xl mx-auto leading-relaxed font-normal">
            Monitor sensor telemetry, predict component failures before they happen with Machine Learning, track DTC fault codes, and prevent catastrophic fleet downtime.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href={token ? "/fleet" : "/register"} className="btn-primary px-8 py-3.5 text-base w-full sm:w-auto justify-center">
              <span>{token ? "Open Fleet Dashboard" : "Start Monitoring Free"}</span>
              <ArrowRight className="w-5 h-5" />
            </Link>
            <Link href="/login" className="btn-secondary px-8 py-3.5 text-base w-full sm:w-auto justify-center">
              Sign In to Demo Account
            </Link>
          </div>

          {/* Stats Bar */}
          <div className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto">
            {[
              { label: "Real-time Telemetry", val: "10+ OBD PIDs" },
              { label: "ML Inference", val: "XGBoost & SHAP" },
              { label: "Live Telemetry Feed", val: "< 1s Latency" },
              { label: "DTC Code Mapping", val: "Standard OBD-II" },
            ].map((stat, i) => (
              <div key={i} className="glass-card p-5 text-center">
                <div className="text-xl sm:text-2xl font-bold font-heading text-accent-sky">{stat.val}</div>
                <div className="text-xs text-text-muted mt-1">{stat.label}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Feature Cards Grid */}
        <section className="py-20 bg-base-surface/40 border-y border-border/40 px-6 lg:px-12">
          <div className="max-w-7xl mx-auto">
            <div className="text-center max-w-2xl mx-auto mb-16">
              <h2 className="text-3xl sm:text-4xl font-bold font-heading">Complete Fleet Intelligence Platform</h2>
              <p className="text-text-muted mt-3">Built for modern automotive fleets, technicians, and predictive maintenance engineering.</p>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              {[
                {
                  icon: Activity,
                  title: "Real-Time Telemetry Streaming",
                  desc: "Stream RPM, oil pressure, coolant temp, vibration, and electrical voltage with WebSocket zero-latency feeds.",
                },
                {
                  icon: Brain,
                  title: "Machine Learning Predictions",
                  desc: "Trained XGBoost and Random Forest models accurately calculate failure risk and provide SHAP feature attribution.",
                },
                {
                  icon: BellRing,
                  title: "Instant Multi-Channel Alerts",
                  desc: "Automatic threshold detection fires instantaneous webhooks and real-time in-app notification toasts.",
                },
                {
                  icon: Truck,
                  title: "Multi-Vehicle Fleet Overview",
                  desc: "Manage multiple vehicles under role-based access control with live individual vehicle health scores.",
                },
                {
                  icon: LineChart,
                  title: "Historical Trend Analytics",
                  desc: "Analyze sensor drift over time, view historical DTC fault codes, and export PDF diagnostics reports.",
                },
                {
                  icon: ShieldCheck,
                  title: "Enterprise Grade Security",
                  desc: "OAuth2 authentication, JWT token revocation blocklists, rate limiting, and encrypted tenant data isolation.",
                },
              ].map((feat, i) => (
                <div key={i} className="glass-card p-8 hover:border-accent-sky/40 transition-all duration-300 group">
                  <div className="w-12 h-12 rounded-xl bg-accent-sky/10 border border-accent-sky/20 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                    <feat.icon className="w-6 h-6 text-accent-sky" />
                  </div>
                  <h3 className="text-xl font-bold font-heading mb-2">{feat.title}</h3>
                  <p className="text-text-muted text-sm leading-relaxed">{feat.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* How It Works */}
        <section className="py-20 px-6 lg:px-12 max-w-7xl mx-auto">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold font-heading">How It Works</h2>
            <p className="text-text-muted mt-3">Get up and running with live vehicle telemetry in 3 simple steps.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              { step: "01", title: "Create Your Fleet Account", text: "Sign up in seconds and register your vehicles by display ID and engine specifications." },
              { step: "02", title: "Connect Telemetry Source", text: "Feed sensor data via REST HTTP API or launch the OBD-II simulator for instant testing." },
              { step: "03", title: "Monitor AI Health Scores", text: "Watch real-time health scores, track active DTC codes, and receive proactive failure warnings." },
            ].map((s, i) => (
              <div key={i} className="glass-card p-8 relative">
                <span className="text-5xl font-extrabold font-heading text-accent-sky/15 absolute top-6 right-6">{s.step}</span>
                <h3 className="text-lg font-bold font-heading mb-3">{s.title}</h3>
                <p className="text-text-muted text-sm leading-relaxed">{s.text}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-border/40 py-8 px-6 lg:px-12 bg-base-surface/60 text-xs text-text-muted">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-accent-sky" />
            <span className="font-heading font-semibold text-text-primary">Vehicle Health Monitor</span>
            <span>— AI-Powered Fleet Diagnostics</span>
          </div>
          <div>© {new Date().getFullYear()} Vehicle Health Monitor. All rights reserved.</div>
        </div>
      </footer>
    </div>
  );
}
