import { apiFetch } from "../apiClient";
import type { Stimulus } from "../types";

export function listStimuli(studyId: string) {
  return apiFetch<Stimulus[]>(`/studies/${studyId}/stimulus`);
}

export function uploadStimulus(
  studyId: string,
  input: { type: string; file?: File | null; sourceUrl?: string | null; metadata?: object | null }
) {
  const formData = new FormData();
  formData.append("type", input.type);
  if (input.file) formData.append("file", input.file);
  if (input.sourceUrl) formData.append("source_url", input.sourceUrl);
  if (input.metadata) formData.append("metadata", JSON.stringify(input.metadata));
  return apiFetch<Stimulus>(`/studies/${studyId}/stimulus`, { formData });
}

export function analyzeStimuli(studyId: string) {
  return apiFetch<{ job_id: string; status: string }[]>(`/studies/${studyId}/stimulus/analyze`, {
    method: "POST",
  });
}
