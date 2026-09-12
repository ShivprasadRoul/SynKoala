import { apiFetch } from "../apiClient";
import type { Study } from "../types";

export function listStudies() {
  return apiFetch<Study[]>("/studies");
}

export function getStudy(studyId: string) {
  return apiFetch<Study>(`/studies/${studyId}`);
}

export function createStudy(input: { name: string; objective?: string | null }) {
  return apiFetch<Study>("/studies", { body: input });
}

export function updateStudy(
  studyId: string,
  input: { name?: string; objective?: string | null; status?: string }
) {
  return apiFetch<Study>(`/studies/${studyId}`, { method: "PATCH", body: input });
}
