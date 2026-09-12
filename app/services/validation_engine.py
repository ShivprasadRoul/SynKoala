"""planning/10-validation-engine.md (HLD §3.I, `04-Evaluation-Spec-Synthetic-Koala.md`).

Pure computation over already-fetched rows — no session/DB access, the same split
as `AnalyticsEngine`/`AudienceEngine`: the job handler
(`app/workers/jobs/validate_run.py`) fetches `human_benchmarks`/`metrics`/
`segment_results` and persists `validation_results`, this class only computes.

Scope: implements planning/10's own Responsibilities list (items 1-6), which is
already narrower than the full Evaluation Spec — §4.4 (navigation/path
similarity, defined-journey alignment) and §5 (confidence calibration) aren't in
planning/10's list or in `validation_results.metric`'s documented vocabulary, and
aren't implemented here.

`comparison="baseline_*"` rows compare the run under validation directly against
that baseline run's own metrics, never against a human benchmark — `03-data-
model-and-infra.md`'s `ValidationResultModel` docstring is explicit that
`human_benchmark_id` is NULL for baseline rows "since those don't require human
data," so a `baseline_random` row means "how far is this run's own behaviour
from a random baseline's," not "how does the baseline compare to human." Useful
side effect: it's computable even for a study with no human benchmark at all.
"""

import math
import statistics
from dataclasses import dataclass, field


@dataclass
class RunSummary:
    """One run's (or one `human_benchmarks` row's) metrics, normalized to the
    one shape every comparison needs. `click_rates`/`attention_shares` are keyed
    by `element_key` (not `element_id`) — a human benchmark upload has no way to
    know a synthetic run's internal UUIDs, `ui_elements.element_key` is the only
    identifier both sides can share."""

    completion_rate: float | None = None
    sample_size: int | None = None
    click_rates: dict[str, float] = field(default_factory=dict)
    attention_shares: dict[str, float] = field(default_factory=dict)


@dataclass
class ValidationRow:
    metric: str
    comparison: str
    value: float
    sample_size: int


def _jensen_shannon_divergence(p: list[float], q: list[float]) -> float:
    """Both inputs must already be normalized to sum to 1 (Evaluation Spec
    §4.3's own instruction) — not re-normalized here so a caller can't
    accidentally skip that step silently."""
    m = [(pi + qi) / 2 for pi, qi in zip(p, q, strict=True)]

    def _kl(a: list[float], b: list[float]) -> float:
        return sum(ai * math.log2(ai / bi) for ai, bi in zip(a, b, strict=True) if ai > 0)

    return 0.5 * _kl(p, m) + 0.5 * _kl(q, m)


def _pearson(x: list[float], y: list[float]) -> float | None:
    """`None`, not a fabricated 0, when either side is constant —
    `statistics.correlation` is undefined (and would mean nothing) for a
    zero-variance series."""
    if len(x) < 2 or len(set(x)) < 2 or len(set(y)) < 2:
        return None
    return statistics.correlation(x, y)


class ValidationEngine:
    """planning/10-validation-engine.md. Stateless, like `AnalyticsEngine`."""

    # ---- Evaluation Spec §4.1/§4.2/§4.3, shared between human and baseline comparisons ----

    def compare_runs(self, comparison: str, a: RunSummary, b: RunSummary) -> list[ValidationRow]:
        """Task completion agreement, click agreement, and attention similarity
        are the same computation whether `b` is a human benchmark or a baseline
        run's own `RunSummary` — only `comparison` (and therefore whether a
        `human_benchmark_id` gets attached) differs, decided by the caller."""
        rows: list[ValidationRow] = []
        completion_row = self._task_completion_agreement(comparison, a, b)
        if completion_row is not None:
            rows.append(completion_row)
        click_row = self._click_agreement(comparison, a.click_rates, b.click_rates)
        if click_row is not None:
            rows.append(click_row)
        rows.extend(self._attention_similarity(comparison, a.attention_shares, b.attention_shares))
        return rows

    def _task_completion_agreement(
        self, comparison: str, a: RunSummary, b: RunSummary
    ) -> ValidationRow | None:
        if a.completion_rate is None or b.completion_rate is None:
            return None
        sample_sizes = [n for n in (a.sample_size, b.sample_size) if n is not None]
        return ValidationRow(
            "task_completion_agreement",
            comparison,
            abs(a.completion_rate - b.completion_rate),
            min(sample_sizes) if sample_sizes else 0,
        )

    def _click_agreement(
        self, comparison: str, a_rates: dict[str, float], b_rates: dict[str, float]
    ) -> ValidationRow | None:
        common = sorted(set(a_rates) & set(b_rates))
        if len(common) < 2:
            return None
        r = _pearson([a_rates[k] for k in common], [b_rates[k] for k in common])
        if r is None:
            return None
        return ValidationRow("click_agreement", comparison, r, len(common))

    def _attention_similarity(
        self, comparison: str, a_shares: dict[str, float], b_shares: dict[str, float]
    ) -> list[ValidationRow]:
        common = sorted(set(a_shares) | set(b_shares))
        if len(common) < 2:
            return []
        a_total = sum(a_shares.get(k, 0.0) for k in common)
        b_total = sum(b_shares.get(k, 0.0) for k in common)
        if a_total <= 0 or b_total <= 0:
            return []
        a_norm = [a_shares.get(k, 0.0) / a_total for k in common]
        b_norm = [b_shares.get(k, 0.0) / b_total for k in common]

        rows: list[ValidationRow] = []
        spatial_corr = _pearson(a_norm, b_norm)
        if spatial_corr is not None:
            rows.append(
                ValidationRow(
                    "attention_spatial_correlation", comparison, spatial_corr, len(common)
                )
            )
        jsd = _jensen_shannon_divergence(a_norm, b_norm)
        rows.append(ValidationRow("attention_jsd_similarity", comparison, 1 - jsd, len(common)))
        return rows

    # ---- Evaluation Spec §4.5 ----

    def segment_directional_agreement(
        self,
        relationships: list[dict] | None,
        segment_values: dict[tuple[str, str], float],
    ) -> ValidationRow | None:
        """`relationships`: `[{"segment_low", "segment_high", "metric",
        "direction": "lower"|"higher"}, ...]` from `human_benchmarks.
        segment_labels["relationships"]` — `segment_low`/`segment_high` are
        expected to name the same segments `AnalyticsEngine.compute_segments`
        produces (e.g. `"digital_confidence_low"`), since that's the only
        segment vocabulary this codebase has. Only the *direction* has to
        match, per the spec — not the magnitude."""
        if not relationships:
            return None
        correct = 0
        total = 0
        for rel in relationships:
            low = segment_values.get((rel["segment_low"], rel["metric"]))
            high = segment_values.get((rel["segment_high"], rel["metric"]))
            if low is None or high is None:
                continue
            total += 1
            if rel["direction"] == "lower" and low < high:
                correct += 1
            elif rel["direction"] == "higher" and low > high:
                correct += 1
        if total == 0:
            return None
        return ValidationRow(
            "segment_directional_agreement", "human_benchmark", correct / total, total
        )

    # ---- Evaluation Spec §4.6 ----

    def run_stability_cv(self, completion_rates: list[float]) -> ValidationRow | None:
        """Requires >= 5 repeated runs of the same study configuration
        (planning/10 item 5's own stated threshold); skipped, not computed on
        fewer, since a CV from 2-3 runs isn't the population-level signal this
        is meant to demonstrate. The one metric that needs no human data at
        all — stochastic attention/action selection (PRD §6) means stability
        has to be demonstrated, not assumed."""
        if len(completion_rates) < 5:
            return None
        mean = statistics.mean(completion_rates)
        if mean == 0:
            return None
        return ValidationRow(
            "run_stability_cv",
            "stability",
            statistics.stdev(completion_rates) / mean,
            len(completion_rates),
        )
