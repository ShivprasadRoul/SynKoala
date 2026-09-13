import uuid
from datetime import UTC, datetime

from app.db.models import SimulationRunModel
from app.services.simulation_run_service import SimulationRunService


class _FakeSession:
    """`finalize_run` issues its `scalar` calls in a fixed order: `get_by_id`,
    then (only when the run isn't CANCELLING) the errored-participant count,
    then the total. A call counter is simpler and less brittle here than trying
    to pattern-match the three different `select(...)` statements themselves."""

    def __init__(
        self, run: SimulationRunModel, errored_count: int = 0, total_count: int = 3
    ) -> None:
        self._run = run
        self._results = [run, errored_count, total_count]
        self._calls = 0

    async def scalar(self, _stmt):
        result = self._results[min(self._calls, len(self._results) - 1)]
        self._calls += 1
        return result

    async def flush(self) -> None:
        pass


def _run(status: str) -> SimulationRunModel:
    return SimulationRunModel(
        id=uuid.uuid4(),
        study_id=uuid.uuid4(),
        population_size=10,
        status=status,
        started_at=datetime.now(UTC),
    )


async def test_finalize_run_sets_cancelled_when_run_was_cancelling():
    """The fix: a run cancelled mid-flight must land on CANCELLED, not
    COMPLETED/FAILED, even if some participants happened to finish
    successfully before the cancel reached them."""
    run = _run("CANCELLING")
    service = SimulationRunService(_FakeSession(run, errored_count=0, total_count=3))

    result = await service.finalize_run(run.id)

    assert result.status == "CANCELLED"
    assert result.completed_at is not None


async def test_finalize_run_sets_completed_when_every_participant_abandoned():
    """A population that all dropped off is a valid result — often the finding
    itself — not a failed simulation. FAILED is reserved for the case where the
    jobs themselves broke, so a 100% abandonment run must still finalize
    COMPLETED and carry its metrics."""
    run = _run("RUNNING")
    service = SimulationRunService(_FakeSession(run, errored_count=0, total_count=4))

    result = await service.finalize_run(run.id)

    assert result.status == "COMPLETED"


async def test_finalize_run_sets_failed_when_every_participant_job_errored():
    run = _run("RUNNING")
    service = SimulationRunService(_FakeSession(run, errored_count=4, total_count=4))

    result = await service.finalize_run(run.id)

    assert result.status == "FAILED"


async def test_finalize_run_sets_completed_when_only_some_participant_jobs_errored():
    """One broken job doesn't invalidate the participants that did simulate —
    their observations are real and still worth aggregating."""
    run = _run("RUNNING")
    service = SimulationRunService(_FakeSession(run, errored_count=1, total_count=4))

    result = await service.finalize_run(run.id)

    assert result.status == "COMPLETED"


async def test_finalize_run_sets_failed_when_the_run_had_no_participants():
    run = _run("RUNNING")
    service = SimulationRunService(_FakeSession(run, errored_count=0, total_count=0))

    result = await service.finalize_run(run.id)

    assert result.status == "FAILED"


async def test_lock_for_finalize_returns_the_run():
    run = _run("RUNNING")
    service = SimulationRunService(_FakeSession(run, errored_count=0, total_count=0))

    result = await service.lock_for_finalize(run.id)

    assert result is run
