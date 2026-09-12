"""planning/11-insight-engine.md (HLD §3.J, LLD §16-17, §26-27,
`04-Evaluation-Spec-Synthetic-Koala.md` §5).

Pure computation over already-fetched rows and an already-synthesized
`InsightSynthesis` — no session/DB access, no model call (that's
`PydanticAIInsightProvider.synthesize`, called once by the job handler,
`app/workers/jobs/generate_insights.py`, between `build_evidence_package` and
`validate`). Same split as `AnalyticsEngine`/`ValidationEngine`/`AudienceEngine`.

Mechanically validates every `InsightDraft` the model returns against the same
evidence it was given (LLD §27) — a citation that doesn't match a real,
sufficiently-sampled `metrics`/`segment_results` row gets the whole insight
rejected outright, never "fixed" by asking the model to retry (that would let
it paper over an unsupported claim). `evidence_strength` (item 4) is computed
here from the validated evidence and `validation_results`, never from the
model's own confidence.
"""

import uuid
from dataclasses import dataclass

from app.agents.providers.insight_provider import (
    EvidencePackage,
    InsightDraft,
    MetricFact,
    PatternFact,
    SegmentFact,
    ValidationFact,
)

MIN_SAMPLE_SIZE = 20

EvidenceLink = tuple[str, uuid.UUID, float]  # (kind: "metric" | "segment", row id, value)


@dataclass
class MetricRecord:
    """One `metrics` row, kept with its own id (unlike `MetricFact`, which is
    what the model sees) so a matched citation can be linked back to it via
    `insight_evidence.metric_id`."""

    id: uuid.UUID
    level: str
    metric: str
    element: str | None
    screen: str | None
    value: float
    sample_size: int


@dataclass
class SegmentRecord:
    id: uuid.UUID
    segment: str
    metric: str
    value: float
    sample_size: int


@dataclass
class ValidatedInsight:
    draft: InsightDraft
    evidence_links: list[EvidenceLink]


class InsightEngine:
    """planning/11-insight-engine.md. Stateless, like `AnalyticsEngine`."""

    def build_evidence_package(
        self,
        study_name: str,
        task_instruction: str,
        metrics: list[MetricRecord],
        segments: list[SegmentRecord],
        validation: list[ValidationFact],
        patterns: list[PatternFact],
    ) -> EvidencePackage:
        """Assembles exactly what `InsightProvider.synthesize` is allowed to
        see — no internal ids (a model citing a UUID back at us would prove
        nothing; natural keys like `metric`/`element`/`segment` are what
        `validate` below re-resolves against the real rows)."""
        return EvidencePackage(
            study_name=study_name,
            task_instruction=task_instruction,
            metrics=[
                MetricFact(
                    level=m.level,
                    metric=m.metric,
                    element=m.element,
                    screen=m.screen,
                    value=m.value,
                    sample_size=m.sample_size,
                )
                for m in metrics
            ],
            segments=[
                SegmentFact(
                    segment=s.segment, metric=s.metric, value=s.value, sample_size=s.sample_size
                )
                for s in segments
            ],
            validation=validation,
            patterns=patterns,
        )

    def validate(
        self,
        draft: InsightDraft,
        metrics: list[MetricRecord],
        segments: list[SegmentRecord],
        min_sample_size: int = MIN_SAMPLE_SIZE,
    ) -> ValidatedInsight | None:
        """LLD §27, in order: every referenced metric/segment must exist,
        every cited value must match the stored aggregate (rounded), every
        segment name (in `evidence` and in `affected_segments`) must exist,
        and every cited row's sample size must clear the minimum. Any failure
        rejects the whole insight — no partial credit."""
        if not draft.evidence:
            return None

        metric_index = {(m.metric, m.element, m.screen): m for m in metrics}
        segment_index = {(s.segment, s.metric): s for s in segments}
        known_segments = {s.segment for s in segments}

        if any(name not in known_segments for name in draft.affected_segments):
            return None

        evidence_links: list[EvidenceLink] = []
        for ref in draft.evidence:
            if ref.segment is not None:
                record = segment_index.get((ref.segment, ref.metric))
                kind = "segment"
            else:
                record = metric_index.get((ref.metric, ref.element, ref.screen))
                kind = "metric"
            if record is None:
                return None
            if round(record.value, 6) != round(ref.value, 6):
                return None
            if record.sample_size < min_sample_size:
                return None
            evidence_links.append((kind, record.id, record.value))

        return ValidatedInsight(draft=draft, evidence_links=evidence_links)

    def compute_evidence_strength(
        self,
        validated: ValidatedInsight,
        metrics: list[MetricRecord],
        segments: list[SegmentRecord],
        validation: list[ValidationFact],
    ) -> dict:
        """Replaces the model's own confidence (PRD §7, LLD §16) with a
        composite computed from the validated evidence and
        `validation_results`. `sample_size`/`effect_size` always come from the
        cited evidence itself; `segment_consistency`/`run_stability`/
        `human_benchmark_agreement` are omitted (never invented) when no
        matching `validation_results` row exists for this run."""
        sample_size = self._min_sample_size(validated, metrics, segments)
        values = [value for _, _, value in validated.evidence_links]
        # A single bounded number standing in for "how big is the effect" across
        # arbitrarily different metrics (a rate, a correlation, an AE) has no one
        # universally correct definition — the strongest single cited value is a
        # simple, defensible, bounded [0,1]-ish proxy, not a cross-metric formula.
        effect_size = max(abs(v) for v in values) if values else 0.0

        strength: dict = {
            "sample_size": sample_size,
            "effect_size": round(effect_size, 4),
        }

        cited_metrics = {ref.metric for ref in validated.draft.evidence}
        segment_agreement = next(
            (
                v
                for v in validation
                if v.metric == "segment_directional_agreement" and v.comparison == "human_benchmark"
            ),
            None,
        )
        if segment_agreement is not None:
            strength["segment_consistency"] = self._bucket(
                segment_agreement.value, high=0.7, medium=0.4
            )

        stability = next(
            (
                v
                for v in validation
                if v.metric == "run_stability_cv" and v.comparison == "stability"
            ),
            None,
        )
        if stability is not None:
            # Lower CV is *more* stable — invert the sense of the bucket thresholds.
            strength["run_stability"] = self._bucket_inverse(stability.value, low=0.35, medium=0.15)

        human_agreement = next(
            (
                v
                for v in validation
                if v.metric in cited_metrics and v.comparison == "human_benchmark"
            ),
            None,
        )
        if human_agreement is not None:
            strength["human_benchmark_agreement"] = human_agreement.value

        qualitative = [self._bucket(sample_size, high=100, medium=30)]
        qualitative.append(self._bucket(effect_size, high=0.3, medium=0.1))
        if "segment_consistency" in strength:
            qualitative.append(strength["segment_consistency"])
        if "run_stability" in strength:
            qualitative.append(strength["run_stability"])
        if "LOW" in qualitative:
            strength["overall"] = "LOW"
        elif all(level == "HIGH" for level in qualitative):
            strength["overall"] = "HIGH"
        else:
            strength["overall"] = "MEDIUM"

        return strength

    def _min_sample_size(
        self,
        validated: ValidatedInsight,
        metrics: list[MetricRecord],
        segments: list[SegmentRecord],
    ) -> int:
        metric_by_id = {m.id: m for m in metrics}
        segment_by_id = {s.id: s for s in segments}
        sizes = []
        for kind, row_id, _ in validated.evidence_links:
            record = metric_by_id.get(row_id) if kind == "metric" else segment_by_id.get(row_id)
            if record is not None:
                sizes.append(record.sample_size)
        return min(sizes) if sizes else 0

    def _bucket(self, value: float, *, high: float, medium: float) -> str:
        if value >= high:
            return "HIGH"
        if value >= medium:
            return "MEDIUM"
        return "LOW"

    def _bucket_inverse(self, value: float, *, low: float, medium: float) -> str:
        if value <= medium:
            return "HIGH"
        if value <= low:
            return "MEDIUM"
        return "LOW"
