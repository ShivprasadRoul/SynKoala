import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import { getSupabaseAnonKey, getSupabaseUrl } from "../settings";

// Built lazily, on first actual use (a creator signing in) — never at module
// load time. createClient() throws synchronously on a blank URL, and doing
// that eagerly at import time crashed the entire app on launch, even for a
// tester who never touches Supabase at all.
export function getSupabaseClient(): SupabaseClient {
  const url = getSupabaseUrl();
  const anonKey = getSupabaseAnonKey();
  if (!url || !anonKey) {
    throw new Error(
      "Supabase isn't configured on this device yet — set it from Home → Settings."
    );
  }
  // No session persistence (no AsyncStorage-backed auth store) — a creator
  // re-logs-in each time the app is opened. Fine for a capture-session tool
  // used in short bursts; not a full auth client like the Web App's.
  return createClient(url, anonKey, {
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
  });
}
