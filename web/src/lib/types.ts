// Mirrors app/domain/schemas/*.py exactly — see planning/12-web-app.md §5 for the
// request/response shapes these types back. Keep in sync with the backend schemas,
// not the other way around.

export const STUDY_STATUSES = ["DRAFT", "READY", "RUNNING", "COMPLETED", "FAILED"] as const;
export type StudyStatus = (typeof STUDY_STATUSES)[number];

export interface Study {
  id: string;
  project_id: string;
  name: string;
  objective: string | null;
  status: StudyStatus;
  population_size: number | null;
  created_at: string;
  updated_at: string;
}

// Bands AudienceEngine understands for digital/behaviour traits
// (app/services/audience_engine.py:_BAND_TO_MEAN_STD) — a researcher picks one of
// these per trait rather than typing a raw mean/std.
export const TRAIT_BANDS = ["low", "low_medium", "medium", "medium_high", "high"] as const;
export type TraitBand = (typeof TRAIT_BANDS)[number];

// The specific shape this app writes into Audience.definition (backend-typed as a
// bare `dict` — app/domain/schemas/audience.py — since AudienceEngine.build_prior
// only reads a few known keys and passes the rest through). `personas` is this app's
// own addition: hand-authored, qualitative target personas, kept alongside the
// statistical prior but never read by AudienceEngine's sampling.
export interface AudienceDefinition {
  demographics?: {
    country?: string;
    language?: string;
    city?: string;
    age_range?: [number, number];
  };
  digital?: {
    confidence?: TraitBand;
    familiarity?: TraitBand;
  };
  behaviour?: {
    exploration?: TraitBand;
    patience?: TraitBand;
    goal_directedness?: TraitBand;
  };
  description?: string;
  personas?: Persona[];
}

// Mirrors app/domain/schemas/audience.py:PersonaCreate exactly — field set matches
// the persona-authoring form this product's team already uses elsewhere.
export interface Persona {
  persona_name: string;
  subtitle: string;
  persona_description?: string;
  age_group: string;
  country: string;
  language: string;
  occupation?: string;
  product_usage?: string;
  brand_affinity?: string;
  lifestyle_behaviour?: string;
  risk_tolerance?: string;
  price_sensitivity?: string;
  novelty_presence?: string;
  emotional_state?: string;
  income_band?: string;
  generation?: string;
  urbanicity?: string;
  purchase_occasion?: string;
  primary_device?: string;
  decision_stage?: string;
  job_to_be_done?: string;
  domain?: Record<string, string>;
  motivations?: string[];
  pain_points?: string[];
  key_decision_trigger?: string[];
  preferred_channels?: string[];
  decision_criteria?: Record<string, string>;
}

export interface Audience {
  id: string;
  study_id: string;
  name: string;
  definition: Record<string, unknown>;
  prior: Record<string, unknown> | null;
  version: number;
  created_at: string;
}

export interface Participant {
  id: string;
  audience_id: string;
  traits: Record<string, unknown>;
  persona: Record<string, unknown> | null;
  seed: number | null;
  created_at: string;
}

export interface Task {
  id: string;
  study_id: string;
  instruction: string;
  starting_point: string | null;
  success_conditions: Record<string, unknown> | null;
  constraints: Record<string, unknown> | null;
  expected_critical_actions: string[] | null;
  intended_path: unknown[] | null;
  created_at: string;
}

export interface UIElement {
  id: string;
  screen_id: string;
  element_key: string;
  type: string;
  text: string | null;
  // [x1, y1, x2, y2] — app/agents/providers/vision_provider.py's BBox shape.
  bbox: [number, number, number, number];
  properties: Record<string, unknown> | null;
  created_at: string;
}

export interface Screen {
  id: string;
  stimulus_id: string;
  screen_key: string;
  width: number | null;
  height: number | null;
  image_url: string | null;
  analysis: Record<string, unknown> | null;
  created_at: string;
  elements: UIElement[];
}

export interface Stimulus {
  id: string;
  study_id: string;
  type: string;
  source_url: string | null;
  metadata: Record<string, unknown> | null;
  version: number;
  created_at: string;
  screens: Screen[];
}

export const SIMULATION_RUN_STATUSES = [
  "PENDING",
  "RUNNING",
  "CANCELLING",
  "CANCELLED",
  "COMPLETED",
  "FAILED",
] as const;
export type SimulationRunStatus = (typeof SIMULATION_RUN_STATUSES)[number];

export interface SimulationRun {
  id: string;
  study_id: string;
  population_size: number;
  status: SimulationRunStatus;
  config: Record<string, unknown> | null;
  model_versions: Record<string, unknown> | null;
  seed: number | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface Metric {
  id: string;
  level: "task_success" | "friction" | "discoverability";
  metric: string;
  element_id: string | null;
  segment: string | null;
  value: number | null;
  sample_size: number | null;
}

export interface MetricsResponse {
  task_success: Metric[];
  friction: Metric[];
  discoverability: Metric[];
}

export interface ApiErrorEnvelope {
  error: {
    code: "NOT_FOUND" | "LIFECYCLE_ERROR" | "VALIDATION_ERROR" | "HTTP_ERROR" | string;
    message: string;
    details: unknown;
  };
}
