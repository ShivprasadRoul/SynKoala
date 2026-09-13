import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ParticipantRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    simulation_run_id: uuid.UUID
    participant_id: uuid.UUID
    status: str
    current_screen_id: uuid.UUID | None
    task_state: dict | None
    final_outcome: dict | None
    started_at: datetime | None
    completed_at: datetime | None


class ObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    participant_run_id: uuid.UUID
    sequence_no: int
    timestamp_ms: int | None
    type: str
    screen_id: uuid.UUID | None
    element_id: uuid.UUID | None
    x: float | None
    y: float | None
    duration_ms: int | None
    payload: dict | None
    created_at: datetime


class MetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    level: str
    metric: str
    element_id: uuid.UUID | None
    screen_id: uuid.UUID | None
    element_key: str | None = None
    screen_key: str | None = None
    segment: str | None
    value: float | None
    sample_size: int | None


class MetricsResponse(BaseModel):
    task_success: list[MetricRead] = []
    friction: list[MetricRead] = []
    discoverability: list[MetricRead] = []


class HeatmapCell(BaseModel):
    screen_id: uuid.UUID | None
    element_id: uuid.UUID | None
    intensity: float
    fixation_count: int


class PathRead(BaseModel):
    participant_run_id: uuid.UUID
    screens: list[uuid.UUID]


class PixelHeatmapCell(BaseModel):
    screen_id: uuid.UUID
    x: float
    y: float
    intensity: float


class ScanpathStep(BaseModel):
    sequence_no: int
    type: str
    screen_id: uuid.UUID | None
    element_id: uuid.UUID | None
    x: float | None
    y: float | None
    duration_ms: int | None
    scan_number: int | None


class ScanpathRead(BaseModel):
    participant_run_id: uuid.UUID
    path: list[ScanpathStep]


class SegmentResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    segment: str
    metric: str
    value: float | None
    sample_size: int | None


class ValidationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    metric: str
    comparison: str
    value: float | None
    sample_size: int | None
    human_benchmark_id: uuid.UUID | None


class ValidationResponse(BaseModel):
    # planning/10-validation-engine.md: "no_benchmark" is a real status, not an
    # empty list — the frontend must be able to tell "not computed" from "computed
    # and empty".
    status: str
    results: list[ValidationResultRead] = []


class InsightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    severity: str
    summary: str
    affected_segments: list[str] | None
    recommendation: str | None
    evidence_strength: dict | None
    created_at: datetime
