"use client";

import type { Session } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useState } from "react";

import { getSupabaseClient } from "@/lib/supabase";

interface AuthContextValue {
  session: Session | null;
  loading: boolean;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  // Computed during render, not in an effect — it's a synchronous check
  // against env config, not something that needs an effect's async/subscribe
  // lifecycle. Only the actual Supabase calls below (async, or a subscription
  // callback) belong in the effect.
  let supabase = null as ReturnType<typeof getSupabaseClient> | null;
  let configError: string | null = null;
  try {
    supabase = getSupabaseClient();
  } catch (err) {
    configError = err instanceof Error ? err.message : "Supabase isn't configured";
  }

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data: subscription } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });
    return () => subscription.subscription.unsubscribe();
  }, [supabase]);

  async function signOut() {
    await getSupabaseClient().auth.signOut();
  }

  if (configError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas px-6">
        <div className="max-w-[440px] border border-hairline bg-surface-1 p-6">
          <h1 className="font-display text-[18px] font-bold text-ink">Supabase not configured</h1>
          <p className="mt-2 text-[14px] text-ink-muted">{configError}</p>
        </div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ session, loading, signOut }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
