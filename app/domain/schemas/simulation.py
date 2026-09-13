import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SimulationRunCreate(BaseModel):
    # Optional: SimulationUseCase.create_run falls back to the study's own
    # population_size (set once at study creation) when omitted, so a repeat
    # run against an already-published study doesn't need this re-typed.
    population_size: int | None = Field(default=None, ge=1, le=1000)
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


class SimulationRunSummary(BaseModel):
    """One row of a study's run history (planning/02-api.md's new `GET
    /studies/:id/simulations`) — enough to render a run list without a
    per-run detail fetch. `completion_rate` is looked up from that run's own
    `metrics` row when the analytics chain has produced one, `None` before
    then (never fabricated — same rule as `ValidationResponse`'s
    `"no_benchmark"` status elsewhere in this module's sibling schemas)."""

    id: uuid.UUID
    status: str
    population_size: int
    source: str
    seed: int | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    completion_rate: float | None
