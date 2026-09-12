import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskCreate(BaseModel):
    instruction: str
    starting_point: str | None = None
    success_conditions: dict | None = None
    constraints: dict | None = None
    expected_critical_actions: list[str] | None = None


class TaskUpdate(BaseModel):
    instruction: str | None = None
    starting_point: str | None = None
    success_conditions: dict | None = None
    constraints: dict | None = None
    expected_critical_actions: list[str] | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    study_id: uuid.UUID
    instruction: str
    starting_point: str | None
    success_conditions: dict | None
    constraints: dict | None
    expected_critical_actions: list[str] | None
    created_at: datetime
