import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SimulationRunCreate(BaseModel):
    population_size: int = Field(ge=1, le=1000)
    task_id: uuid.UUID | None = None
    config: dict | None = None
    seed: int | None = None


class SimulationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    study_id: uuid.UUID
    population_size: int
    status: str
    config: dict | None
    model_versions: dict | None
    seed: int | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
