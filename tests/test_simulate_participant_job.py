import uuid
from unittest.mock import AsyncMock, Mock

from app.workers.jobs import simulate_participant as job_module


def _fake_runs_service() -> AsyncMock:
    """`_finalize_run_and_notify` always builds a `pg_notify` payload from
    `count_terminal`/`count_total`, whatever else a test cares about — an
    unconfigured `AsyncMock` there fails `json.dumps`, not the assertion."""
    fake = AsyncMock()
    fake.count_terminal.return_value = 1
    fake.count_total.return_value = 3
    return fake


class _FakeSession:
    """Only `.execute()` (the `pg_notify` call) is exercised — `SimulationRunService`/
    `JobService` are monkeypatched out where the job constructs them itself."""

    async def execute(self, stmt, params=None):
        return None


# --- handle_simulate_participant_permanent_failure --------------------------------


async def test_permanent_failure_marks_a_dangling_participant_run_failed(monkeypatch):
    """The gap this closes: a job that fails before ever reaching
    `complete_participant_run` (e.g. the "no analyzed screens yet" error) must
    not leave its participant_runs row PENDING forever, or the run could never
    finalize (planning/06-study-orchestrator.md item 4)."""
    participant_run = Mock(status="PENDING")
    run = Mock(status="RUNNING")

    fake_runs = _fake_runs_service()
    fake_runs.get_participant_run.return_value = participant_run
    fake_runs.is_run_complete.return_value = False
    fake_runs.get_by_id.return_value = run
    fake_jobs = AsyncMock()

    monkeypatch.setattr(job_module, "SimulationRunService", lambda session: fake_runs)
    monkeypatch.setattr(job_module, "JobService", lambda session: fake_jobs)

    await job_module.handle_simulate_participant_permanent_failure(
        _FakeSession(),
        {"simulation_run_id": str(uuid.uuid4()), "participant_run_id": str(uuid.uuid4())},
    )

    fake_runs.complete_participant_run.assert_awaited_once()
    _, kwargs = fake_runs.complete_participant_run.await_args
    assert kwargs["status"] == "FAILED"


async def test_permanent_failure_is_a_noop_for_an_already_terminal_participant_run(monkeypatch):
    """If the handler's own last attempt already reached its terminal-status
    write before raising, this must not overwrite it (e.g. a COMPLETED
    participant shouldn't be flipped to FAILED just because the job row itself
    retried past that point due to something after it, like the NOTIFY call)."""
    participant_run = Mock(status="COMPLETED")
    run = Mock(status="RUNNING")
    fake_runs = _fake_runs_service()
    fake_runs.get_participant_run.return_value = participant_run
    fake_runs.is_run_complete.return_value = False
    fake_runs.get_by_id.return_value = run
    fake_jobs = AsyncMock()

    monkeypatch.setattr(job_module, "SimulationRunService", lambda session: fake_runs)
    monkeypatch.setattr(job_module, "JobService", lambda session: fake_jobs)

    await job_module.handle_simulate_participant_permanent_failure(
        _FakeSession(),
        {"simulation_run_id": str(uuid.uuid4()), "participant_run_id": str(uuid.uuid4())},
    )

    fake_runs.complete_participant_run.assert_not_awaited()


# --- _finalize_run_and_notify -------------------------------------------------------


async def test_finalize_run_and_notify_enqueues_aggregate_run_once_completed():
    run_id = uuid.uuid4()
    completed_run = Mock(status="COMPLETED")
    fake_runs = _fake_runs_service()
    fake_runs.is_run_complete.return_value = True
    fake_runs.finalize_run.return_value = completed_run
    fake_runs.get_by_id.return_value = completed_run
    fake_jobs = AsyncMock()

    await job_module._finalize_run_and_notify(_FakeSession(), fake_runs, fake_jobs, run_id)

    fake_jobs.enqueue.assert_awaited_once_with("aggregate_run", {"simulation_run_id": str(run_id)})


async def test_finalize_run_and_notify_enqueues_aggregate_run_even_when_every_participant_failed():
    """A FAILED run (finalize_run's own status when zero participants
    completed) must still get analyzed — 0% completion is a real,
    headline-level result the Analytics Engine's friction/discoverability
    metrics exist to explain, not a reason to skip analysis entirely."""
    run_id = uuid.uuid4()
    failed_run = Mock(status="FAILED")
    fake_runs = _fake_runs_service()
    fake_runs.is_run_complete.return_value = True
    fake_runs.finalize_run.return_value = failed_run
    fake_runs.get_by_id.return_value = failed_run
    fake_jobs = AsyncMock()

    await job_module._finalize_run_and_notify(_FakeSession(), fake_runs, fake_jobs, run_id)

    fake_jobs.enqueue.assert_awaited_once_with("aggregate_run", {"simulation_run_id": str(run_id)})


async def test_finalize_run_and_notify_does_not_enqueue_aggregate_run_when_cancelled():
    """Unlike FAILED, a CANCELLED run was explicitly interrupted by the
    researcher, not left to reach its own terminal state — its data isn't a
    genuine population result, so it's still excluded from analysis."""
    run_id = uuid.uuid4()
    cancelled_run = Mock(status="CANCELLED")
    fake_runs = _fake_runs_service()
    fake_runs.is_run_complete.return_value = True
    fake_runs.finalize_run.return_value = cancelled_run
    fake_runs.get_by_id.return_value = cancelled_run
    fake_jobs = AsyncMock()

    await job_module._finalize_run_and_notify(_FakeSession(), fake_runs, fake_jobs, run_id)

    fake_jobs.enqueue.assert_not_awaited()


async def test_finalize_run_and_notify_skips_finalize_while_participants_remain():
    run_id = uuid.uuid4()
    running_run = Mock(status="RUNNING")
    fake_runs = _fake_runs_service()
    fake_runs.is_run_complete.return_value = False
    fake_runs.get_by_id.return_value = running_run
    fake_jobs = AsyncMock()

    await job_module._finalize_run_and_notify(_FakeSession(), fake_runs, fake_jobs, run_id)

    fake_runs.finalize_run.assert_not_awaited()
    fake_jobs.enqueue.assert_not_awaited()
