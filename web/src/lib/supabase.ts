import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let cached: SupabaseClient | null = null;

// Built lazily, on first actual use — never at module load time.
// createClient() throws synchronously on a blank URL, and doing that eagerly
// at import time crashes the whole app (every page, via the root layout's
// AuthProvider) before anything renders if NEXT_PUBLIC_SUPABASE_URL/
// NEXT_PUBLIC_SUPABASE_ANON_KEY aren't set in web/.env.local.
export function getSupabaseClient(): SupabaseClient {
  if (cached) return cached;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    throw new Error(
      "Supabase isn't configured — set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in web/.env.local (see web/.env.example)."
    );
  }
  // Default (persisted) session storage — one browser tab, unlike mobile/'s
  // deliberately unpersisted client for a shared-device capture tool.
  cached = createClient(url, anonKey);
  return cached;
}
