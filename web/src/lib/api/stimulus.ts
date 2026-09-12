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

// Uploads several screenshots in one request — each becomes its own stimulus/
// screen, named from its own filename, exactly like uploadStimulus does one
// at a time (app/usecases/stimulus.py:create_bulk).
export function bulkUploadStimuli(studyId: string, input: { type: string; files: File[] }) {
  const formData = new FormData();
  formData.append("type", input.type);
  for (const file of input.files) formData.append("files", file);
  return apiFetch<Stimulus[]>(`/studies/${studyId}/stimulus/bulk`, { formData });
}

export function analyzeStimuli(studyId: string) {
  return apiFetch<{ job_id: string; status: string }[]>(`/studies/${studyId}/stimulus/analyze`, {
    method: "POST",
  });
}
