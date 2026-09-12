import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HumanBenchmarkModel, ValidationResultModel
from app.services.benchmark_service import BenchmarkService
from app.services.job_service import JobService
from app.services.results_service import ResultsService
from app.services.simulation_run_service import SimulationRunService
from app.services.stimulus_service import StimulusService
from app.services.validation_engine import RunSummary, ValidationEngine

_BASELINE_TYPES = ("random", "saliency_only", "task_only")


def _participant_model_of(run) -> str:
    return (run.config or {}).get("participant_model") or "heuristic"


async def _run_summary(
    results: ResultsService, run_id: uuid.UUID, element_key_by_id: dict[uuid.UUID, str]
) -> RunSummary:
    metrics_by_level = await results.get_metrics(run_id)
    flat = [m for level in metrics_by_level.values() for m in level]
    completion = next((m for m in flat if m.metric == "completion_rate"), None)
    return RunSummary(
        completion_rate=completion.value if completion else None,
        sample_size=completion.sample_size if completion else None,
        click_rates={
            element_key_by_id[m.element_id]: m.value
            for m in flat
            if m.metric == "click_rate"
            and m.element_id in element_key_by_id
            and m.value is not None
        },
        attention_shares={
            element_key_by_id[m.element_id]: m.value
            for m in flat
            if m.metric == "attention_share"
            and m.element_id in element_key_by_id
            and m.value is not None
        },
    )


def _run_summary_from_benchmark(benchmark: HumanBenchmarkModel) -> RunSummary:
    """Normalizes a freeform `human_benchmarks` row into the same shape a
    synthetic run's own metrics produce (planning/10's own convention, since
    nothing else constrains this JSONB's shape): `task_outcomes =
    {"completion_rate": float, "sample_size": int}`, `interaction_rates =
    {"<element_key>": rate}`, `attention_data = {"elements": {"<element_key>":
    share}}`."""
    task_outcomes = benchmark.task_outcomes or {}
    attention = (benchmark.attention_data or {}).get("elements", {})
    return RunSummary(
        completion_rate=task_outcomes.get("completion_rate"),
        sample_size=task_outcomes.get("sample_size"),
        click_rates=dict(benchmark.interaction_rates or {}),
        attention_shares=dict(attention),
    )


async def handle_validate_run(session: AsyncSession, payload: dict) -> None:
    """The Validation Engine's job (planning/10-validation-engine.md): runs
    after `aggregate_run`. Computes Evaluation Spec §4.1/§4.2/§4.3 against the
    study's `human_benchmarks` row (if any) and against any completed baseline
    runs for the same study+task, §4.5's segment directional agreement against
    `human_benchmarks.segment_labels`, and §4.6's run-to-run stability CV across
    completed siblings of the same participant model — enqueues
    `generate_insights` (planning/11, also real now) regardless of whether any
    of that had data to work with, since validation is optional evidence, not
    a gate (planning/10's own "Job" section)."""
    run_id = uuid.UUID(payload["simulation_run_id"])

    runs = SimulationRunService(session)
    results = ResultsService(session)
    stimuli = StimulusService(session)
    benchmarks = BenchmarkService(session)
    jobs = JobService(session)
    engine = ValidationEngine()

    run = await runs.get_by_id(run_id)
    element_key_by_id = await stimuli.get_element_key_map(run.study_id)
    main_summary = await _run_summary(results, run_id, element_key_by_id)
    segment_values = {
        (s.segment, s.metric): s.value
        for s in await results.list_segment_results(run_id)
        if s.value is not None
    }
    siblings = await runs.list_sibling_runs(run.study_id, run.task_id, exclude_run_id=run_id)

    rows = []

    benchmark = await benchmarks.get_latest_for_study_or_none(run.study_id)
    if benchmark is not None:
        benchmark_summary = _run_summary_from_benchmark(benchmark)
        rows.extend(engine.compare_runs("human_benchmark", main_summary, benchmark_summary))
        agreement = engine.segment_directional_agreement(
            (benchmark.segment_labels or {}).get("relationships"), segment_values
        )
        if agreement is not None:
            rows.append(agreement)

    current_model = _participant_model_of(run)
    for baseline_type in _BASELINE_TYPES:
        if baseline_type == current_model:
            continue
        baseline_run = next(
            (s for s in siblings if _participant_model_of(s) == baseline_type), None
        )
        if baseline_run is None:
            continue
        baseline_summary = await _run_summary(results, baseline_run.id, element_key_by_id)
        rows.extend(
            engine.compare_runs(f"baseline_{baseline_type}", main_summary, baseline_summary)
        )

    stability_siblings = [s for s in siblings if _participant_model_of(s) == current_model]
    completion_rates = (
        [main_summary.completion_rate] if main_summary.completion_rate is not None else []
    )
    for sibling in stability_siblings:
        sibling_summary = await _run_summary(results, sibling.id, element_key_by_id)
        if sibling_summary.completion_rate is not None:
            completion_rates.append(sibling_summary.completion_rate)
    stability_row = engine.run_stability_cv(completion_rates)
    if stability_row is not None:
        rows.append(stability_row)

    # Idempotent under retry, same reasoning as aggregate_run.
    await session.execute(
        delete(ValidationResultModel).where(ValidationResultModel.simulation_run_id == run_id)
    )
    session.add_all(
        ValidationResultModel(
            simulation_run_id=run_id,
            human_benchmark_id=(
                benchmark.id
                if benchmark is not None and row.comparison == "human_benchmark"
                else None
            ),
            metric=row.metric,
            comparison=row.comparison,
            value=row.value,
            sample_size=row.sample_size,
        )
        for row in rows
    )

    await jobs.enqueue("generate_insights", {"simulation_run_id": str(run_id)})
