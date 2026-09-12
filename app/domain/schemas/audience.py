import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AudienceCreate(BaseModel):
    name: str
    definition: dict


class PersonaCreate(BaseModel):
    """A hand-authored, qualitative target persona attached to an audience's
    `definition["personas"]` (`AudienceUseCase.add_persona`) — descriptive
    colour for the researcher, not a trait-sampling input; `AudienceEngine`
    never reads this. Field set matches the persona-authoring form this
    product's team already uses elsewhere, so a researcher moving between
    tools sees the same vocabulary."""

    model_config = ConfigDict(extra="forbid")

    persona_name: str = Field(..., min_length=1)
    subtitle: str = Field(..., min_length=1)
    persona_description: str | None = None
    age_group: str = Field(..., description="Single number (25) or range (25-30)")
    country: str = Field(..., min_length=1)
    language: str = Field(..., min_length=1)
    occupation: str | None = None
    product_usage: str | None = None
    brand_affinity: str | None = None
    lifestyle_behaviour: str | None = None
    risk_tolerance: str | None = None
    price_sensitivity: str | None = None
    novelty_presence: str | None = None
    emotional_state: str | None = None
    income_band: str | None = None
    generation: str | None = None
    urbanicity: str | None = None
    purchase_occasion: str | None = None
    primary_device: str | None = None
    decision_stage: str | None = None
    job_to_be_done: str | None = None
    domain: dict[str, str] = Field(default_factory=dict)
    motivations: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    key_decision_trigger: list[str] = Field(default_factory=list)
    preferred_channels: list[str] = Field(default_factory=list)
    decision_criteria: dict[str, str] = Field(default_factory=dict)

    @field_validator("age_group")
    @classmethod
    def validate_age_group(cls, value: str) -> str:
        if not re.match(r"^\d+$|^\d+-\d+$", value):
            raise ValueError("age_group must be a single number or a range like 25-30")
        return value


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
