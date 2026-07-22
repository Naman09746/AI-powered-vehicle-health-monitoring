"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Page() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/fleet");
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-screen bg-base">
      <div className="animate-pulse text-text-muted">Redirecting...</div>
    </div>
  );
}
