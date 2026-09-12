import { apiFetch } from "../apiClient";
import type { Study } from "../types";

export function listStudies() {
  return apiFetch<Study[]>("/studies");
}

export function getStudy(studyId: string) {
  return apiFetch<Study>(`/studies/${studyId}`);
}

export function createStudy(input: {
  name: string;
  objective?: string | null;
  population_size?: number | null;
}) {
  return apiFetch<Study>("/studies", { body: input });
}

export function updateStudy(
  studyId: string,
  input: {
    name?: string;
    objective?: string | null;
    status?: string;
    population_size?: number | null;
  }
) {
  return apiFetch<Study>(`/studies/${studyId}`, { method: "PATCH", body: input });
}

// Soft-delete (app/services/study_service.py sets deleted_at, doesn't drop the
// row) — 204 No Content, apiFetch resolves that to undefined.
export function deleteStudy(studyId: string): Promise<void> {
  return apiFetch<void>(`/studies/${studyId}`, { method: "DELETE" });
}
