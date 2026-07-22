"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";

export default function Home() {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);

  useEffect(() => {
    if (token) {
      router.replace("/fleet");
    } else {
      router.replace("/login");
    }
  }, [token, router]);

  return (
    <div className="flex items-center justify-center min-h-screen bg-base">
      <div className="animate-pulse text-text-muted">Loading...</div>
    </div>
  );
}
