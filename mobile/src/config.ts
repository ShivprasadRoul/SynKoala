// EXPO_PUBLIC_-prefixed vars are inlined at build time by Expo — no extra
// package needed. Set them in mobile/.env (see mobile/.env.example) or your
// shell before `npx expo start`.
export const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
export const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL ?? "";
export const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? "";
