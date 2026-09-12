import AsyncStorage from "@react-native-async-storage/async-storage";

import {
  API_BASE_URL as BUILD_TIME_API_BASE_URL,
  SUPABASE_ANON_KEY as BUILD_TIME_SUPABASE_ANON_KEY,
  SUPABASE_URL as BUILD_TIME_SUPABASE_URL,
} from "./config";

// None of these can be safely baked in at build time for a distributed APK:
// the backend's LAN address is per-tester-machine and changes with the
// network, and — as a real crash surfaced — a missing/blank Supabase URL
// throws synchronously from createClient() at module-load time, crashing the
// whole app before any screen renders, even for someone only using Tester
// mode (which never touches Supabase at all). Everything here is therefore
// settable after install, not just at build time.
const STORAGE_KEYS = {
  apiBaseUrl: "synkoala.apiBaseUrl",
  supabaseUrl: "synkoala.supabaseUrl",
  supabaseAnonKey: "synkoala.supabaseAnonKey",
};

let cache = {
  apiBaseUrl: BUILD_TIME_API_BASE_URL,
  supabaseUrl: BUILD_TIME_SUPABASE_URL,
  supabaseAnonKey: BUILD_TIME_SUPABASE_ANON_KEY,
};
let loaded = false;

export async function loadSettings(): Promise<void> {
  if (loaded) return;
  const [apiBaseUrl, supabaseUrl, supabaseAnonKey] = await Promise.all([
    AsyncStorage.getItem(STORAGE_KEYS.apiBaseUrl),
    AsyncStorage.getItem(STORAGE_KEYS.supabaseUrl),
    AsyncStorage.getItem(STORAGE_KEYS.supabaseAnonKey),
  ]);
  cache = {
    apiBaseUrl: apiBaseUrl || BUILD_TIME_API_BASE_URL,
    supabaseUrl: supabaseUrl || BUILD_TIME_SUPABASE_URL,
    supabaseAnonKey: supabaseAnonKey || BUILD_TIME_SUPABASE_ANON_KEY,
  };
  loaded = true;
}

export function getApiBaseUrl(): string {
  return cache.apiBaseUrl;
}

export async function setApiBaseUrl(url: string): Promise<void> {
  cache = { ...cache, apiBaseUrl: url };
  await AsyncStorage.setItem(STORAGE_KEYS.apiBaseUrl, url);
}

export function getSupabaseUrl(): string {
  return cache.supabaseUrl;
}

export function getSupabaseAnonKey(): string {
  return cache.supabaseAnonKey;
}

export async function setSupabaseConfig(url: string, anonKey: string): Promise<void> {
  cache = { ...cache, supabaseUrl: url, supabaseAnonKey: anonKey };
  await Promise.all([
    AsyncStorage.setItem(STORAGE_KEYS.supabaseUrl, url),
    AsyncStorage.setItem(STORAGE_KEYS.supabaseAnonKey, anonKey),
  ]);
}
