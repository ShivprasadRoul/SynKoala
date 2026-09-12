import { ApiError, apiFetch } from "../apiClient";
import type { Audience, Participant } from "../types";

// GET .../audience returns the single latest AudienceRead, not a list — a study
// has at most one "current" audience definition (app/api/v1/audiences.py).
export async function getAudience(studyId: string): Promise<Audience | null> {
  try {
    return await apiFetch<Audience>(`/studies/${studyId}/audience`);
  } catch (err) {
    if (err instanceof ApiError && err.code === "NOT_FOUND") return null;
    throw err;
  }
}

export function createAudience(studyId: string, input: { name: string; definition: object }) {
  return apiFetch<Audience>(`/studies/${studyId}/audience`, { body: input });
}

// Adds to the population — it doesn't replace it, and there's no endpoint to list
// the cumulative total (planning/12-web-app.md §5.2), so callers only learn the
// size of the batch just generated, not a running total.
export function generatePopulation(
  studyId: string,
  input: { population_size: number; seed?: number | null }
) {
  return apiFetch<Participant[]>(`/studies/${studyId}/audience/generate`, { body: input });
}
