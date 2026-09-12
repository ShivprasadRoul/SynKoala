import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UIElementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    screen_id: uuid.UUID
    element_key: str
    type: str
    text: str | None
    bbox: dict
    properties: dict | None
    created_at: datetime


class ScreenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stimulus_id: uuid.UUID
    screen_key: str
    width: int | None
    height: int | None
    image_url: str | None
    analysis: dict | None
    created_at: datetime
    elements: list[UIElementRead] = []


class StimulusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    study_id: uuid.UUID
    type: str
    source_url: str | None
    metadata: dict | None = Field(validation_alias="metadata_", default=None)
    version: int
    created_at: datetime
    screens: list[ScreenRead] = []


class AnalyzeJobRead(BaseModel):
    job_id: uuid.UUID
    status: str = "PENDING"
