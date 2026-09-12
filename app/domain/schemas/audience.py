import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AudienceCreate(BaseModel):
    name: str
    definition: dict


class AudienceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    study_id: uuid.UUID
    name: str
    definition: dict
    prior: dict | None
    version: int
    created_at: datetime


class GenerateAudienceRequest(BaseModel):
    population_size: int = Field(ge=1, le=1000)
    seed: int | None = None


class ParticipantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    audience_id: uuid.UUID
    traits: dict
    persona: dict | None
    seed: int | None
    created_at: datetime
