import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class IntendedPathStep(BaseModel):
    screen_figma_node_id: str
    element_figma_node_id: str | None = None
    action: Literal["TAP", "SCROLL", "BACK"]
    duration_ms: int


class IntendedPathSet(BaseModel):
    steps: list[IntendedPathStep]


class IntendedPathRead(BaseModel):
    steps: list[IntendedPathStep]


class CaptureSessionCreate(BaseModel):
    tester_label: str | None = None


class CaptureSessionRead(BaseModel):
    participant_run_id: uuid.UUID
    capture_token: str


class ObservationCreate(BaseModel):
    sequence_no: int
    type: str
    screen_figma_node_id: str | None = None
    element_figma_node_id: str | None = None
    x: float | None = None
    y: float | None = None
    duration_ms: int | None = None
    payload: dict | None = None


class ObservationRead(BaseModel):
    id: int


class ParticipantRunComplete(BaseModel):
    status: Literal["COMPLETED", "FAILED", "ABANDONED"]
    final_outcome: dict | None = None


class ParticipantRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    simulation_run_id: uuid.UUID
    tester_label: str | None
    status: str
    final_outcome: dict | None
    voice_note_url: str | None
    started_at: datetime | None
    completed_at: datetime | None
