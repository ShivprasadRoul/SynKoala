import { getSupabaseClient } from "./supabase";
import type { ApiErrorEnvelope } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  details: unknown;
  status: number;

  constructor(status: number, envelope: ApiErrorEnvelope["error"]) {
    super(envelope.message);
    this.name = "ApiError";
    this.status = status;
    this.code = envelope.code;
    this.details = envelope.details;
  }
}

interface FetchOptions {
  method?: string;
  body?: unknown;
  formData?: FormData;
}

async function currentAccessToken(): Promise<string | null> {
  const { data } = await getSupabaseClient().auth.getSession();
  return data.session?.access_token ?? null;
}

async function doFetch(path: string, token: string | null, options: FetchOptions) {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (options.formData) {
    body = options.formData;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  return fetch(`${API_BASE_URL}/api/v1${path}`, {
    method: options.method ?? (body ? "POST" : "GET"),
    headers,
    body,
  });
}

/**
 * Attaches the current Supabase session's access token (planning/12-web-app.md §3),
 * parses the backend's {error:{code,message,details}} envelope on failure (§4), and
 * retries once after an explicit session refresh on a 401 before giving up.
 */
export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  let token = await currentAccessToken();
  let response = await doFetch(path, token, options);

  if (response.status === 401) {
    const { data } = await getSupabaseClient().auth.refreshSession();
    token = data.session?.access_token ?? null;
    response = await doFetch(path, token, options);
  }

  if (!response.ok) {
    const envelope = (await response.json().catch(() => null)) as ApiErrorEnvelope | null;
    throw new ApiError(
      response.status,
      envelope?.error ?? { code: "HTTP_ERROR", message: response.statusText, details: null }
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
