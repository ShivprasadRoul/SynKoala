import { apiFetch } from "../apiClient";
import type { MetricsResponse, SimulationRun, SimulationRunSummary } from "../types";

// population_size is optional: SimulationUseCase.create_run falls back to the
// study's own population_size (set once at study creation) when omitted, so
// a repeat run against a published study doesn't need it re-entered.
export function createSimulationRun(
  studyId: string,
  input: { population_size?: number | null; task_id?: string | null; seed?: number | null } = {}
) {
  return apiFetch<SimulationRun>(`/studies/${studyId}/simulations`, { body: input });
}

export function listSimulationRuns(studyId: string) {
  return apiFetch<SimulationRunSummary[]>(`/studies/${studyId}/simulations`);
}

// Publishes a DRAFT study and starts its first simulation run in one request
// (SimulationUseCase.publish) — replaces the old "PATCH status=READY" flow,
// which only flipped a status flag and never actually started anything.
export function publishStudy(studyId: string) {
  return apiFetch<SimulationRun>(`/studies/${studyId}/publish`, { method: "POST" });
}

export function getSimulationRun(runId: string) {
  return apiFetch<SimulationRun>(`/simulations/${runId}`);
}

export function cancelSimulationRun(runId: string) {
  return apiFetch<SimulationRun>(`/simulations/${runId}/cancel`, { method: "POST" });
}

export function getMetrics(runId: string) {
  return apiFetch<MetricsResponse>(`/simulations/${runId}/metrics`);
}

const TERMINAL_STATUSES = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

export function isTerminalRunStatus(status: string): boolean {
  return TERMINAL_STATUSES.has(status);
}
