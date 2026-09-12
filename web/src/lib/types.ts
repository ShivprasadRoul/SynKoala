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
// these per trait rather than typing a raw mean/std. The UI only offers the three
// coarse bands (low/medium/high) per the audience-module spec; the backend also
// accepts low_medium/medium_high for finer-grained callers.
export const TRAIT_BANDS = ["low", "medium", "high"] as const;
export type TraitBand = (typeof TRAIT_BANDS)[number];

// The specific shape this app writes into Audience.definition (backend-typed as a
// bare `dict` — app/domain/schemas/audience.py — since AudienceEngine.build_prior
// only reads a few known keys and passes the rest through). Audience != Persona:
// this is only the statistical population definition — no persona-level fields
// (name, occupation, motivations, etc.) belong here. Personas are sampled from
// this definition via "Generate Personas", not hand-authored alongside it.
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

// Mirrors app/services/persona_sampler.py:PersonaSampler.sample's return shape
// exactly. Every numeric field is 0.0-1.0, sampled deterministically from the
// audience's distribution (plus a formula over those same core traits for the
// fields the audience doesn't define directly) — never from an LLM, so the
// same seed always reproduces the same personas. Identity fields are cosmetic
// flavor only; mental_model/goal are grounded in the study's real Task text
// where one exists.
export interface GeneratedPersona {
  persona_id: string;
  identity: {
    name: string;
    age: number;
    occupation: string;
    location: string;
  };
  context: {
    digital_confidence: number;
    product_familiarity: number;
    domain_experience: number;
    usage_frequency: string;
    primary_device: string;
  };
  behavior: {
    digital_confidence: number;
    exploration: number;
    patience: number;
    goal_directedness: number;
    decision_speed: number;
    cta_recognition: number;
    search_tendency: number;
    backtracking_tendency: number;
    error_recovery: number;
    instruction_following: number;
  };
  mental_model: {
    expected_action: string;
    expected_location: string;
    expected_terminology: string[];
    navigation_expectation: string;
  };
  goal: {
    primary_goal: string;
    motivation: string;
    urgency: number;
    success_definition: string;
  };
  friction: {
    confusion_threshold: number;
    abandonment_threshold: number;
    retry_probability: number;
    alternative_path_probability: number;
    help_seeking_probability: number;
  };
  ui_preferences: {
    text_comprehension: number;
    icon_reliance: number;
    form_tolerance: number;
    modal_tolerance: number;
    scrolling_tolerance: number;
    icon_only_cta_recognition: number;
  };
}

export interface Participant {
  id: string;
  audience_id: string;
  traits: Record<string, unknown>;
  persona: GeneratedPersona | null;
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

// app/domain/schemas/benchmark.py — optional per study (planning/12-web-app.md
// §5.5). `task_outcomes`/`interaction_rates`/`segment_labels`/`attention_data`
// are all freeform JSONB backend-side; this app only ever writes/reads
// `task_outcomes.completion_rate` (the one field the Validation Engine's
// task_completion_agreement formula needs), leaving the rest as raw JSON a
// researcher can paste in.
export interface Benchmark {
  id: string;
  study_id: string;
  source: string | null;
  task_outcomes: Record<string, unknown> | null;
  interaction_rates: Record<string, unknown> | null;
  segment_labels: Record<string, unknown> | null;
  attention_data: Record<string, unknown> | null;
  version: number;
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
