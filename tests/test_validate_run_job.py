import uuid
from unittest.mock import AsyncMock, Mock

from app.workers.jobs import validate_run as job_module


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list = []
        self.added: list = []

    async def execute(self, stmt) -> None:
        self.executed.append(stmt)

    def add_all(self, rows) -> None:
        self.added.extend(rows)


def _metric(level, metric, value, element_id=None, sample_size=10):
    # A plain dict, not a Mock — ResultsService.get_metrics really returns
    # dicts (element_key/screen_key enrichment, planning/09), and this test
    # fixture using attribute-style Mocks instead is exactly what let
    # validate_run.py's own attribute access (`m.metric`) drift out of sync
    # with the real contract without any test catching it.
    return {
        "id": uuid.uuid4(),
        "level": level,
        "metric": metric,
        "element_id": element_id,
        "screen_id": None,
        "value": value,
        "sample_size": sample_size,
    }


def _metrics_response(completion_rate, click_rates=None, attention_shares=None):
    click_rates = click_rates or {}
    attention_shares = attention_shares or {}
    discoverability = [
        _metric("discoverability", "click_rate", v, element_id=k) for k, v in click_rates.items()
    ] + [
        _metric("discoverability", "attention_share", v, element_id=k)
        for k, v in attention_shares.items()
    ]
    return {
        "task_success": [_metric("task_success", "completion_rate", completion_rate)],
        "friction": [],
        "discoverability": discoverability,
    }


def _patch_services(monkeypatch, *, run, siblings, metrics_by_run_id, segment_results, benchmark):
    fake_runs = AsyncMock()
    fake_runs.get_by_id.return_value = run
    fake_runs.list_sibling_runs.return_value = siblings
    fake_results = AsyncMock()
    fake_results.get_metrics.side_effect = lambda run_id: metrics_by_run_id[run_id]
    fake_results.list_segment_results.return_value = segment_results
    fake_stimuli = AsyncMock()
    fake_stimuli.get_element_key_map.return_value = {}
    fake_benchmarks = AsyncMock()
    fake_benchmarks.get_latest_for_study_or_none.return_value = benchmark
    fake_jobs = AsyncMock()

    monkeypatch.setattr(job_module, "SimulationRunService", lambda session: fake_runs)
    monkeypatch.setattr(job_module, "ResultsService", lambda session: fake_results)
    monkeypatch.setattr(job_module, "StimulusService", lambda session: fake_stimuli)
    monkeypatch.setattr(job_module, "BenchmarkService", lambda session: fake_benchmarks)
    monkeypatch.setattr(job_module, "JobService", lambda session: fake_jobs)
    return fake_jobs


async def test_validate_run_computes_human_benchmark_agreement(monkeypatch):
    run_id = uuid.uuid4()
    run = Mock(id=run_id, study_id=uuid.uuid4(), task_id=uuid.uuid4(), config=None)
    benchmark = Mock(
        id=uuid.uuid4(),
        task_outcomes={"completion_rate": 0.5, "sample_size": 30},
        interaction_rates={},
        attention_data={},
        segment_labels=None,
    )

    fake_jobs = _patch_services(
        monkeypatch,
        run=run,
        siblings=[],
        metrics_by_run_id={run_id: _metrics_response(completion_rate=0.6)},
        segment_results=[],
        benchmark=benchmark,
    )
    session = _FakeSession()

    await job_module.handle_validate_run(session, {"simulation_run_id": str(run_id)})

    assert len(session.executed) == 1  # idempotency delete
    rows = session.added
    completion_row = next(r for r in rows if r.metric == "task_completion_agreement")
    assert completion_row.comparison == "human_benchmark"
    assert round(completion_row.value, 4) == 0.1
    assert completion_row.human_benchmark_id == benchmark.id
    fake_jobs.enqueue.assert_awaited_once_with(
        "generate_insights", {"simulation_run_id": str(run_id)}
    )


async def test_validate_run_skips_human_metrics_without_a_benchmark(monkeypatch):
    run_id = uuid.uuid4()
    run = Mock(id=run_id, study_id=uuid.uuid4(), task_id=uuid.uuid4(), config=None)

    fake_jobs = _patch_services(
        monkeypatch,
        run=run,
        siblings=[],
        metrics_by_run_id={run_id: _metrics_response(completion_rate=0.6)},
        segment_results=[],
        benchmark=None,
    )
    session = _FakeSession()

    await job_module.handle_validate_run(session, {"simulation_run_id": str(run_id)})

    assert not [r for r in session.added if r.comparison == "human_benchmark"]
    fake_jobs.enqueue.assert_awaited_once()


async def test_validate_run_compares_against_a_baseline_sibling(monkeypatch):
    run_id = uuid.uuid4()
    baseline_id = uuid.uuid4()
    study_id = uuid.uuid4()
    run = Mock(id=run_id, study_id=study_id, task_id=uuid.uuid4(), config=None)
    baseline_run = Mock(id=baseline_id, config={"participant_model": "random"})

    fake_jobs = _patch_services(
        monkeypatch,
        run=run,
        siblings=[baseline_run],
        metrics_by_run_id={
            run_id: _metrics_response(completion_rate=0.7),
            baseline_id: _metrics_response(completion_rate=0.3),
        },
        segment_results=[],
        benchmark=None,
    )
    session = _FakeSession()

    await job_module.handle_validate_run(session, {"simulation_run_id": str(run_id)})

    baseline_row = next(
        r
        for r in session.added
        if r.metric == "task_completion_agreement" and r.comparison == "baseline_random"
    )
    assert round(baseline_row.value, 4) == 0.4
    assert baseline_row.human_benchmark_id is None
    fake_jobs.enqueue.assert_awaited_once()


async def test_validate_run_computes_stability_across_five_or_more_same_model_siblings(monkeypatch):
    run_id = uuid.uuid4()
    study_id = uuid.uuid4()
    run = Mock(id=run_id, study_id=study_id, task_id=uuid.uuid4(), config=None)
    sibling_ids = [uuid.uuid4() for _ in range(4)]
    siblings = [Mock(id=sid, config=None) for sid in sibling_ids]

    metrics_by_run_id = {run_id: _metrics_response(completion_rate=0.5)}
    for sid in sibling_ids:
        metrics_by_run_id[sid] = _metrics_response(completion_rate=0.5)

    fake_jobs = _patch_services(
        monkeypatch,
        run=run,
        siblings=siblings,
        metrics_by_run_id=metrics_by_run_id,
        segment_results=[],
        benchmark=None,
    )
    session = _FakeSession()

    await job_module.handle_validate_run(session, {"simulation_run_id": str(run_id)})

    stability_row = next(r for r in session.added if r.metric == "run_stability_cv")
    assert stability_row.comparison == "stability"
    assert stability_row.sample_size == 5  # main run + 4 siblings
    fake_jobs.enqueue.assert_awaited_once()


async def test_validate_run_is_idempotent_and_always_enqueues_generate_insights(monkeypatch):
    """Even with nothing computable at all (no benchmark, no siblings, no
    completion metric), the job must still delete stale rows and move the
    chain forward — validation is optional evidence, not a gate."""
    run_id = uuid.uuid4()
    run = Mock(id=run_id, study_id=uuid.uuid4(), task_id=None, config=None)

    fake_jobs = _patch_services(
        monkeypatch,
        run=run,
        siblings=[],
        metrics_by_run_id={run_id: _metrics_response(completion_rate=None)},
        segment_results=[],
        benchmark=None,
    )
    session = _FakeSession()

    await job_module.handle_validate_run(session, {"simulation_run_id": str(run_id)})

    assert session.added == []
    assert len(session.executed) == 1
    fake_jobs.enqueue.assert_awaited_once_with(
        "generate_insights", {"simulation_run_id": str(run_id)}
    )
