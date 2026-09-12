"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/providers/AuthProvider";

export default function RootPage() {
  const { session, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(session ? "/dashboard" : "/login");
  }, [loading, session, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas">
      <p className="text-sm text-ink-subtle">Loading…</p>
    </div>
  );
}
