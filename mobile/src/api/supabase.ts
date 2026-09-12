import { createClient } from "@supabase/supabase-js";

import { SUPABASE_ANON_KEY, SUPABASE_URL } from "../config";

// No session persistence (no AsyncStorage dependency) — a creator re-logs-in
// each time the app is opened. Fine for a capture-session tool used in short
// bursts; not a full auth client like the Web App's.
export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
});
