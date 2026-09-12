import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

STUDY_STATUSES = ("DRAFT", "READY", "RUNNING", "COMPLETED", "FAILED")

# PRD FR-01: DRAFT -> READY -> RUNNING -> COMPLETED / FAILED. No skipping ahead, and no
# leaving a terminal state — enforced in the service layer (see LifecycleError).
STUDY_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "DRAFT": ("READY",),
    "READY": ("RUNNING", "DRAFT"),
    "RUNNING": ("COMPLETED", "FAILED"),
    "COMPLETED": (),
    "FAILED": (),
}


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class StudyCreate(BaseModel):
    name: str
    objective: str | None = None
    population_size: int | None = Field(
        default=None, ge=1, le=1000, description="Intended sample size for this study's runs"
    )


class StudyUpdate(BaseModel):
    name: str | None = None
    objective: str | None = None
    status: str | None = Field(default=None, description="Must be a valid lifecycle transition")
    population_size: int | None = Field(default=None, ge=1, le=1000)


class StudyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    objective: str | None
    status: str
    population_size: int | None
    created_at: datetime
    updated_at: datetime
