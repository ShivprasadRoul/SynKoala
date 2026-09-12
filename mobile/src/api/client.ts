import { getApiBaseUrl } from "../settings";

export type Auth =
  | { kind: "bearer"; token: string }
  | { kind: "capture"; token: string }
  | { kind: "none" };

interface FetchOptions {
  method?: string;
  body?: unknown;
  formData?: FormData;
}

export async function apiFetch<T>(path: string, auth: Auth, options: FetchOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (auth.kind === "bearer") headers.Authorization = `Bearer ${auth.token}`;
  if (auth.kind === "capture") headers["X-Capture-Token"] = auth.token;

  let body: BodyInit | undefined;
  if (options.formData) {
    body = options.formData;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  const response = await fetch(`${getApiBaseUrl()}/api/v1${path}`, {
    method: options.method ?? (body ? "POST" : "GET"),
    headers,
    body,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`${path} failed (${response.status}): ${text}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
