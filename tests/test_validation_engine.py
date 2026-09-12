from app.services.validation_engine import RunSummary, ValidationEngine


def _row(rows, metric, comparison="human_benchmark"):
    return next(r for r in rows if r.metric == metric and r.comparison == comparison)


class TestCompareRuns:
    def test_task_completion_agreement_is_absolute_error(self):
        a = RunSummary(completion_rate=0.6, sample_size=40)
        b = RunSummary(completion_rate=0.5, sample_size=25)
        rows = ValidationEngine().compare_runs("human_benchmark", a, b)
        row = _row(rows, "task_completion_agreement")
        assert round(row.value, 4) == 0.1
        assert row.sample_size == 25  # the smaller of the two

    def test_task_completion_agreement_skipped_without_both_sides(self):
        a = RunSummary(completion_rate=None)
        b = RunSummary(completion_rate=0.5)
        rows = ValidationEngine().compare_runs("human_benchmark", a, b)
        assert not [r for r in rows if r.metric == "task_completion_agreement"]

    def test_click_agreement_is_pearson_correlation_over_common_elements(self):
        a = RunSummary(click_rates={"cta": 0.9, "help": 0.1, "search": 0.5})
        b = RunSummary(click_rates={"cta": 0.8, "help": 0.2, "search": 0.5, "extra": 0.3})
        rows = ValidationEngine().compare_runs("human_benchmark", a, b)
        row = _row(rows, "click_agreement")
        assert row.sample_size == 3  # "extra" isn't common to both
        assert row.value > 0.9  # strongly correlated by construction

    def test_click_agreement_skipped_with_fewer_than_two_common_elements(self):
        a = RunSummary(click_rates={"cta": 0.9})
        b = RunSummary(click_rates={"cta": 0.8, "help": 0.2})
        rows = ValidationEngine().compare_runs("human_benchmark", a, b)
        assert not [r for r in rows if r.metric == "click_agreement"]

    def test_click_agreement_skipped_when_one_side_is_constant(self):
        a = RunSummary(click_rates={"cta": 0.5, "help": 0.5})
        b = RunSummary(click_rates={"cta": 0.8, "help": 0.2})
        rows = ValidationEngine().compare_runs("human_benchmark", a, b)
        assert not [r for r in rows if r.metric == "click_agreement"]

    def test_attention_similarity_produces_spatial_correlation_and_jsd_rows(self):
        a = RunSummary(attention_shares={"cta": 800, "help": 200})
        b = RunSummary(attention_shares={"cta": 750, "help": 250})
        rows = ValidationEngine().compare_runs("human_benchmark", a, b)
        spatial = _row(rows, "attention_spatial_correlation")
        jsd = _row(rows, "attention_jsd_similarity")
        assert spatial.sample_size == 2
        assert 0.0 <= jsd.value <= 1.0
        assert jsd.value > 0.9  # near-identical normalized distributions

    def test_attention_similarity_skipped_when_a_side_has_no_dwell(self):
        a = RunSummary(attention_shares={"cta": 0.0, "help": 0.0})
        b = RunSummary(attention_shares={"cta": 750, "help": 250})
        rows = ValidationEngine().compare_runs("human_benchmark", a, b)
        assert not [r for r in rows if r.metric.startswith("attention_")]

    def test_baseline_comparison_uses_the_given_comparison_label(self):
        a = RunSummary(completion_rate=0.6, sample_size=10)
        b = RunSummary(completion_rate=0.3, sample_size=10)
        rows = ValidationEngine().compare_runs("baseline_random", a, b)
        row = _row(rows, "task_completion_agreement", comparison="baseline_random")
        assert round(row.value, 4) == 0.3


class TestSegmentDirectionalAgreement:
    def test_counts_correctly_predicted_relationships(self):
        relationships = [
            {
                "segment_low": "digital_confidence_low",
                "segment_high": "digital_confidence_high",
                "metric": "completion_rate",
                "direction": "lower",
            },
            {
                "segment_low": "digital_confidence_low",
                "segment_high": "digital_confidence_high",
                "metric": "backtrack_rate",
                "direction": "higher",
            },
        ]
        segment_values = {
            ("digital_confidence_low", "completion_rate"): 0.3,
            ("digital_confidence_high", "completion_rate"): 0.8,
            ("digital_confidence_low", "backtrack_rate"): 0.1,  # wrong direction
            ("digital_confidence_high", "backtrack_rate"): 0.4,
        }
        row = ValidationEngine().segment_directional_agreement(relationships, segment_values)
        assert row.value == 0.5
        assert row.sample_size == 2

    def test_returns_none_without_relationships(self):
        assert ValidationEngine().segment_directional_agreement(None, {}) is None

    def test_skips_relationships_with_missing_segment_data(self):
        relationships = [
            {
                "segment_low": "unknown_low",
                "segment_high": "unknown_high",
                "metric": "completion_rate",
                "direction": "lower",
            }
        ]
        assert ValidationEngine().segment_directional_agreement(relationships, {}) is None


class TestRunStabilityCv:
    def test_requires_at_least_five_runs(self):
        assert ValidationEngine().run_stability_cv([0.5, 0.6, 0.55, 0.52]) is None

    def test_computes_coefficient_of_variation(self):
        rates = [0.5, 0.5, 0.5, 0.5, 0.5]
        row = ValidationEngine().run_stability_cv(rates)
        assert row.value == 0.0
        assert row.sample_size == 5

    def test_returns_none_when_mean_is_zero(self):
        assert ValidationEngine().run_stability_cv([0.0, 0.0, 0.0, 0.0, 0.0]) is None
