import { apiFetch } from "../apiClient";
import type {
  HeatmapCell,
  InsightRead,
  ParticipantRunRead,
  PathRead,
  PixelHeatmapCell,
  ScanpathRead,
  SegmentResultRead,
  ValidationResponse,
} from "../types";

export function getParticipantRuns(runId: string) {
  return apiFetch<ParticipantRunRead[]>(`/simulations/${runId}/participants`);
}

export function getHeatmap(runId: string) {
  return apiFetch<HeatmapCell[]>(`/simulations/${runId}/heatmap`);
}

export function getPixelHeatmap(runId: string, segment?: string | null) {
  const query = segment ? `?segment=${encodeURIComponent(segment)}` : "";
  return apiFetch<PixelHeatmapCell[]>(`/simulations/${runId}/heatmap/pixels${query}`);
}

export function getPaths(runId: string) {
  return apiFetch<PathRead[]>(`/simulations/${runId}/paths`);
}

export function getScanpaths(runId: string) {
  return apiFetch<ScanpathRead[]>(`/simulations/${runId}/scanpaths`);
}

export function getSegments(runId: string) {
  return apiFetch<SegmentResultRead[]>(`/simulations/${runId}/segments`);
}

export function getValidation(runId: string) {
  return apiFetch<ValidationResponse>(`/simulations/${runId}/validation`);
}

export function getInsights(runId: string) {
  return apiFetch<InsightRead[]>(`/simulations/${runId}/insights`);
}
