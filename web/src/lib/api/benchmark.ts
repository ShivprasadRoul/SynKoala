import { ApiError, apiFetch } from "../apiClient";
import type { Benchmark } from "../types";

// GET .../benchmark 404s until one has ever been uploaded for this study
// (app/services/benchmark_service.py has no row to return) — same "not an
// error, just doesn't exist yet" handling as getAudience.
export async function getBenchmark(studyId: string): Promise<Benchmark | null> {
  try {
    return await apiFetch<Benchmark>(`/studies/${studyId}/benchmark`);
  } catch (err) {
    if (err instanceof ApiError && err.code === "NOT_FOUND") return null;
    throw err;
  }
}

// Upserts — re-uploading bumps `version` server-side rather than erroring
// (app/services/benchmark_service.py:upsert).
export function uploadBenchmark(
  studyId: string,
  input: {
    source?: string | null;
    task_outcomes?: Record<string, unknown> | null;
    interaction_rates?: Record<string, unknown> | null;
    segment_labels?: Record<string, unknown> | null;
    attention_data?: Record<string, unknown> | null;
  }
) {
  return apiFetch<Benchmark>(`/studies/${studyId}/benchmark`, { body: input });
}
