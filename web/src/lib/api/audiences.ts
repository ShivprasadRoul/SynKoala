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

// Adds to the population — it doesn't replace it. The response is just the
// batch just generated; call listParticipants for the running total (what a
// page refresh needs to show everything generated so far, not just this call).
export function generatePopulation(
  studyId: string,
  input: { population_size: number; seed?: number | null }
) {
  return apiFetch<Participant[]>(`/studies/${studyId}/audience/generate`, { body: input });
}

// Every participant/persona generated so far for the study's current audience
// — persisted by generatePopulation, read back here (app/api/v1/audiences.py's
// list_participants) so a page refresh doesn't lose them.
export function listParticipants(studyId: string): Promise<Participant[]> {
  return apiFetch<Participant[]>(`/studies/${studyId}/audience/participants`);
}
