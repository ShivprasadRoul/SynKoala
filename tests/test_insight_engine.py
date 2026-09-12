import uuid

from app.agents.providers.insight_provider import EvidenceRef, InsightDraft, ValidationFact
from app.services.insight_engine import InsightEngine, MetricRecord, SegmentRecord

CTA_METRIC_ID = uuid.uuid4()
HOME_SCREEN_METRIC_ID = uuid.uuid4()
SEGMENT_LOW_ID = uuid.uuid4()
SEGMENT_HIGH_ID = uuid.uuid4()


def _metrics() -> list[MetricRecord]:
    return [
        MetricRecord(
            id=CTA_METRIC_ID,
            level="discoverability",
            metric="first_attention_rate",
            element="cta",
            screen=None,
            value=0.21,
            sample_size=40,
        ),
        MetricRecord(
            id=HOME_SCREEN_METRIC_ID,
            level="friction",
            metric="dead_end_rate",
            element=None,
            screen="home",
            value=0.5,
            sample_size=40,
        ),
    ]


def _segments() -> list[SegmentRecord]:
    return [
        SegmentRecord(
            id=SEGMENT_LOW_ID,
            segment="digital_confidence_low",
            metric="backtrack_rate",
            value=0.31,
            sample_size=25,
        ),
        SegmentRecord(
            id=SEGMENT_HIGH_ID,
            segment="digital_confidence_high",
            metric="backtrack_rate",
            value=0.1,
            sample_size=25,
        ),
    ]


def _draft(**overrides) -> InsightDraft:
    defaults = dict(
        title="Users struggle to discover the primary action",
        severity="HIGH",
        summary="The CTA is rarely the first thing attended to.",
        evidence=[EvidenceRef(metric="first_attention_rate", element="cta", value=0.21)],
        affected_segments=[],
        recommendation="Improve CTA prominence.",
    )
    defaults.update(overrides)
    return InsightDraft(**defaults)


class TestBuildEvidencePackage:
    def test_strips_internal_ids_from_the_model_facing_view(self):
        evidence = InsightEngine().build_evidence_package(
            "Study", "Add a shoe to cart", _metrics(), _segments(), [], []
        )
        assert evidence.metrics[0].element == "cta"
        assert not hasattr(evidence.metrics[0], "id")


class TestValidate:
    def test_accepts_a_draft_whose_evidence_matches_a_real_metric(self):
        validated = InsightEngine().validate(_draft(), _metrics(), _segments())
        assert validated is not None
        assert validated.evidence_links == [("metric", CTA_METRIC_ID, 0.21)]

    def test_rejects_an_insight_with_no_evidence_at_all(self):
        assert InsightEngine().validate(_draft(evidence=[]), _metrics(), _segments()) is None

    def test_rejects_a_citation_whose_metric_does_not_exist(self):
        draft = _draft(evidence=[EvidenceRef(metric="made_up_metric", element="cta", value=0.21)])
        assert InsightEngine().validate(draft, _metrics(), _segments()) is None

    def test_rejects_a_citation_whose_value_does_not_match_the_stored_aggregate(self):
        draft = _draft(
            evidence=[EvidenceRef(metric="first_attention_rate", element="cta", value=0.99)]
        )
        assert InsightEngine().validate(draft, _metrics(), _segments()) is None

    def test_rejects_a_citation_below_the_minimum_sample_size(self):
        thin_metrics = [
            MetricRecord(
                id=CTA_METRIC_ID,
                level="discoverability",
                metric="first_attention_rate",
                element="cta",
                screen=None,
                value=0.21,
                sample_size=5,
            )
        ]
        assert InsightEngine().validate(_draft(), thin_metrics, _segments()) is None

    def test_rejects_an_unknown_affected_segment_name(self):
        draft = _draft(affected_segments=["not_a_real_segment"])
        assert InsightEngine().validate(draft, _metrics(), _segments()) is None

    def test_accepts_a_screen_level_citation_for_dead_end_rate(self):
        draft = _draft(
            evidence=[EvidenceRef(metric="dead_end_rate", screen="home", value=0.5)],
            affected_segments=[],
        )
        validated = InsightEngine().validate(draft, _metrics(), _segments())
        assert validated is not None
        assert validated.evidence_links == [("metric", HOME_SCREEN_METRIC_ID, 0.5)]

    def test_accepts_a_segment_citation(self):
        draft = _draft(
            evidence=[
                EvidenceRef(metric="backtrack_rate", segment="digital_confidence_low", value=0.31)
            ],
            affected_segments=["digital_confidence_low"],
        )
        validated = InsightEngine().validate(draft, _metrics(), _segments())
        assert validated is not None
        assert validated.evidence_links == [("segment", SEGMENT_LOW_ID, 0.31)]


class TestComputeEvidenceStrength:
    def test_omits_validation_derived_fields_when_no_validation_results_exist(self):
        validated = InsightEngine().validate(_draft(), _metrics(), _segments())
        strength = InsightEngine().compute_evidence_strength(validated, _metrics(), _segments(), [])
        assert strength["sample_size"] == 40
        assert strength["effect_size"] == 0.21
        assert "segment_consistency" not in strength
        assert "run_stability" not in strength
        assert "human_benchmark_agreement" not in strength
        assert strength["overall"] in ("LOW", "MEDIUM", "HIGH")

    def test_copies_human_benchmark_agreement_for_a_cited_metric(self):
        validation = [
            ValidationFact(
                metric="first_attention_rate",
                comparison="human_benchmark",
                value=0.87,
                sample_size=40,
            )
        ]
        validated = InsightEngine().validate(_draft(), _metrics(), _segments())
        strength = InsightEngine().compute_evidence_strength(
            validated, _metrics(), _segments(), validation
        )
        assert strength["human_benchmark_agreement"] == 0.87

    def test_high_sample_size_and_effect_size_and_stability_rolls_up_to_high(self):
        rich_metrics = [
            MetricRecord(
                id=CTA_METRIC_ID,
                level="discoverability",
                metric="first_attention_rate",
                element="cta",
                screen=None,
                value=0.9,
                sample_size=200,
            )
        ]
        draft = _draft(
            evidence=[EvidenceRef(metric="first_attention_rate", element="cta", value=0.9)]
        )
        validation = [
            ValidationFact(
                metric="segment_directional_agreement",
                comparison="human_benchmark",
                value=0.9,
                sample_size=10,
            ),
            ValidationFact(
                metric="run_stability_cv", comparison="stability", value=0.05, sample_size=5
            ),
        ]
        validated = InsightEngine().validate(draft, rich_metrics, _segments())
        strength = InsightEngine().compute_evidence_strength(
            validated, rich_metrics, _segments(), validation
        )
        assert strength["segment_consistency"] == "HIGH"
        assert strength["run_stability"] == "HIGH"
        assert strength["overall"] == "HIGH"

    def test_a_low_bucket_anywhere_forces_overall_low(self):
        validated = InsightEngine().validate(_draft(), _metrics(), _segments())
        validation = [
            ValidationFact(
                metric="segment_directional_agreement",
                comparison="human_benchmark",
                value=0.1,
                sample_size=10,
            )
        ]
        strength = InsightEngine().compute_evidence_strength(
            validated, _metrics(), _segments(), validation
        )
        assert strength["segment_consistency"] == "LOW"
        assert strength["overall"] == "LOW"
