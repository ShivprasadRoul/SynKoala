// EXPO_PUBLIC_-prefixed vars are inlined at build time by Expo — no extra
// package needed. Set them in mobile/.env (see mobile/.env.example) or your
// shell before `npx expo start`.
export const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
export const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL ?? "";
export const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? "";
// Figma's *Embed API* client id (Figma dashboard -> your app -> Embed API), distinct
// from the backend's OAuth FIGMA_CLIENT_ID (docs/figma-setup.md) -- this one unlocks
// the richer postMessage events (e.g. PRESENTED_NODE_CHANGED) FigmaCaptureView listens
// for. Without it, Figma's embed only sends bare pass-through events.
export const FIGMA_EMBED_CLIENT_ID = process.env.EXPO_PUBLIC_FIGMA_EMBED_CLIENT_ID ?? "";
