import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BenchmarkUpload(BaseModel):
    source: str | None = None
    task_outcomes: dict | None = None
    interaction_rates: dict | None = None
    segment_labels: dict | None = None
    attention_data: dict | None = None


class BenchmarkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    study_id: uuid.UUID
    source: str | None
    task_outcomes: dict | None
    interaction_rates: dict | None
    segment_labels: dict | None
    attention_data: dict | None
    version: int
    created_at: datetime
