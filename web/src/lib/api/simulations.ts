import { apiFetch } from "../apiClient";
import type { MetricsResponse, SimulationRun } from "../types";

export function createSimulationRun(
  studyId: string,
  input: { population_size: number; task_id?: string | null; seed?: number | null }
) {
  return apiFetch<SimulationRun>(`/studies/${studyId}/simulations`, { body: input });
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
