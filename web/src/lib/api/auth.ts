import { apiFetch } from "../apiClient";

// Returns the Figma OAuth authorize URL rather than redirecting itself — this
// call has to carry the caller's Bearer token (app/api/v1/auth.py:figma_authorize),
// which only an authenticated fetch can attach; the actual top-level redirect to
// Figma has to be done by the caller via window.location.
export async function getFigmaAuthorizeUrl(): Promise<string> {
  const { authorize_url } = await apiFetch<{ authorize_url: string }>("/auth/figma/authorize");
  return authorize_url;
}
