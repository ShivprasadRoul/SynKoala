import { apiFetch } from "./client";
import type {
  CaptureSession,
  IntendedPathStep,
  ObservationInput,
  ParticipantRun,
  SimulationRun,
  Study,
  Task,
} from "../types";

// Creator-authenticated (Supabase bearer token) — mirrors app/api/v1/*.py and
// app/api/v1/journey_capture.py on the backend.

export function listStudies(token: string) {
  return apiFetch<Study[]>("/studies", { kind: "bearer", token });
}

export function listTasks(token: string, studyId: string) {
  return apiFetch<Task[]>(`/studies/${studyId}/tasks`, { kind: "bearer", token });
}

export function submitIntendedPath(
  token: string,
  studyId: string,
  taskId: string,
  steps: IntendedPathStep[]
) {
  return apiFetch<Task>(
    `/studies/${studyId}/tasks/${taskId}/intended-path`,
    { kind: "bearer", token },
    { body: { steps } }
  );
}

export function createHumanRun(token: string, studyId: string, taskId: string) {
  return apiFetch<SimulationRun>(
    `/studies/${studyId}/tasks/${taskId}/human-runs`,
    { kind: "bearer", token },
    { method: "POST" }
  );
}

export function createCaptureSession(token: string, runId: string, testerLabel: string | null) {
  return apiFetch<CaptureSession>(
    `/human-runs/${runId}/sessions`,
    { kind: "bearer", token },
    { body: { tester_label: testerLabel } }
  );
}

// Capture-token-authenticated — called by the tester's own device, no login.

export function submitObservation(
  captureToken: string,
  participantRunId: string,
  observation: ObservationInput
) {
  return apiFetch<{ id: number }>(
    `/participant-runs/${participantRunId}/observations`,
    { kind: "capture", token: captureToken },
    { body: observation }
  );
}

export function completeSession(
  captureToken: string,
  participantRunId: string,
  status: "COMPLETED" | "FAILED" | "ABANDONED",
  finalOutcome?: Record<string, unknown>
) {
  return apiFetch<ParticipantRun>(
    `/participant-runs/${participantRunId}/complete`,
    { kind: "capture", token: captureToken },
    { body: { status, final_outcome: finalOutcome ?? null } }
  );
}

export function uploadVoiceNote(captureToken: string, participantRunId: string, fileUri: string) {
  const formData = new FormData();
  // React Native's FormData accepts this {uri,name,type} shape for file parts;
  // it isn't a real Blob/File, hence the cast.
  formData.append("file", { uri: fileUri, name: "voice-note.m4a", type: "audio/m4a" } as unknown as Blob);
  return apiFetch<ParticipantRun>(
    `/participant-runs/${participantRunId}/voice-note`,
    { kind: "capture", token: captureToken },
    { formData }
  );
}
