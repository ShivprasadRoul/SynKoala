"""LLD §28 `InsightProvider` protocol, plus the real implementation
(planning/11-insight-engine.md).

Unlike `VisionProvider`, the model here never touches a screenshot or a raw
observation — only the structured `EvidencePackage` an earlier step
(`InsightEngine.build_evidence_package`, `app/services/insight_engine.py`)
assembles from `metrics`/`segment_results`/`validation_results`/`patterns`
(HLD §1's key rule: never `Screenshot -> LLM -> Insight`, this is
`Observations -> Aggregation -> LLM -> Insight`). And unlike `VisionProvider`'s
output, an `InsightDraft` is never persisted as-is — `InsightEngine.validate`
mechanically checks every `EvidenceRef` against the same `EvidencePackage`
before anything reaches `insights`/`insight_evidence` (LLD §27).
"""

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel
from pydantic_ai import Agent

from app.core.settings import settings


class MetricFact(BaseModel):
    """One `metrics` row, evidence-package form — `element`/`screen` are the
    stable `element_key`/`screen_key` (never a synthetic run's internal UUID,
    which would mean nothing to the model and couldn't be cited back)."""

    level: str
    metric: str
    element: str | None = None
    screen: str | None = None
    value: float
    sample_size: int


class SegmentFact(BaseModel):
    segment: str
    metric: str
    value: float
    sample_size: int


class ValidationFact(BaseModel):
    metric: str
    comparison: str
    value: float
    sample_size: int


class PatternFact(BaseModel):
    pattern_type: str
    payload: dict


class EvidencePackage(BaseModel):
    """Everything `PydanticAIInsightProvider.synthesize` is allowed to see — no
    raw observations, no screenshots, per HLD §1."""

    study_name: str
    task_instruction: str
    metrics: list[MetricFact]
    segments: list[SegmentFact]
    validation: list[ValidationFact]
    patterns: list[PatternFact]


class EvidenceRef(BaseModel):
    metric: str
    element: str | None = None
    # Not in the LLD §16 pseudocode's `EvidenceRef` — added so a `dead_end_rate`
    # citation (per-screen, not per-element, see `metrics.screen_id`) can be
    # checked at all; without it there'd be no way to tell which `MetricFact`
    # a screen-level claim refers to.
    screen: str | None = None
    segment: str | None = None
    value: float


class InsightDraft(BaseModel):
    title: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    summary: str
    evidence: list[EvidenceRef]
    affected_segments: list[str]
    recommendation: str


class InsightSynthesis(BaseModel):
    insights: list[InsightDraft]


@runtime_checkable
class InsightProvider(Protocol):
    async def synthesize(self, evidence: EvidencePackage) -> InsightSynthesis: ...


_SYSTEM_PROMPT = (
    "You are a UX research analyst synthesizing insights from a synthetic-population "
    "usability study. You will be given a structured evidence package — computed "
    "task-success/friction/discoverability metrics, audience-segment comparisons, "
    "human-benchmark validation results, and detected patterns. You have NOT been "
    "given any screenshot, raw event log, or transcript, and must not describe or "
    "invent one. Every insight you report must cite the exact metric/segment/value "
    "combinations you were given as evidence — never a number, element, or segment "
    "name that isn't present verbatim in the evidence package. If the evidence is too "
    "thin to say anything supportable, return fewer insights (including zero) rather "
    "than stretching a claim beyond what the numbers show. Severity should reflect "
    "how much the finding threatens task success, not how surprising it is."
)


class PydanticAIInsightProvider:
    def __init__(self, model: str | None = None) -> None:
        self._model = model or settings.insight_model

    async def synthesize(self, evidence: EvidencePackage) -> InsightSynthesis:
        agent = Agent(self._model, output_type=InsightSynthesis, system_prompt=_SYSTEM_PROMPT)
        result = await agent.run([f"Evidence package: {evidence.model_dump_json()}"])
        return result.output
