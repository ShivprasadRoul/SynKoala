export interface Study {
  id: string;
  project_id: string;
  name: string;
  objective: string | null;
  status: string;
}

export interface Task {
  id: string;
  study_id: string;
  instruction: string;
  intended_path: IntendedPathStep[] | null;
}

export type CapturedAction = "TAP" | "SCROLL" | "BACK";

export interface IntendedPathStep {
  screen_figma_node_id: string;
  element_figma_node_id: string | null;
  action: CapturedAction;
  duration_ms: number;
}

export interface SimulationRun {
  id: string;
  study_id: string;
  status: string;
  source: string;
}

export interface CaptureSession {
  participant_run_id: string;
  capture_token: string;
}

export interface ObservationInput {
  sequence_no: number;
  type: CapturedAction;
  screen_figma_node_id?: string | null;
  element_figma_node_id?: string | null;
  x?: number | null;
  y?: number | null;
  duration_ms?: number | null;
  payload?: Record<string, unknown> | null;
}

export interface ParticipantRun {
  id: string;
  simulation_run_id: string;
  tester_label: string | null;
  status: string;
  final_outcome: Record<string, unknown> | null;
  voice_note_url: string | null;
}
