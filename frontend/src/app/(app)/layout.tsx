"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { ToastContainer } from "@/components/shared/ToastContainer";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const [hydrated, setHydrated] = useState(false);
  const [showSpinner, setShowSpinner] = useState(false);

  useEffect(() => {
    // Wait for Zustand persist to hydrate from localStorage
    const unsub = useAuthStore.persist.onFinishHydration(() => setHydrated(true));
    if (useAuthStore.persist.hasHydrated()) setHydrated(true);
    return () => unsub();
  }, []);

  useEffect(() => {
    if (hydrated && !token) {
      router.replace("/login");
    }
  }, [hydrated, token, router]);

  useEffect(() => {
    if (!hydrated || !token) {
      const timer = setTimeout(() => {
        setShowSpinner(true);
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [hydrated, token]);

  if (!hydrated || !token) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-base">
        {showSpinner && (
          <div className="animate-fade-in flex flex-col items-center gap-2">
            <LoadingSpinner size="lg" label="Loading application..." />
            <span className="text-text-muted text-sm font-medium">Authenticating...</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-base">
      <Sidebar />
      <div className="lg:pl-60">
        <Topbar />
        <main id="main-content" className="p-6 lg:p-8" tabIndex={-1}>{children}</main>
        <ToastContainer />
      </div>
    </div>
  );
}
