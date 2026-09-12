import uuid
from datetime import UTC, datetime

from app.db.models import SimulationRunModel
from app.services.simulation_run_service import SimulationRunService


class _FakeSession:
    """`get_by_id`'s `scalar` call always comes first; the succeeded-count
    query (only reached when the run isn't CANCELLING) comes second — a call
    counter is simpler and less brittle here than trying to pattern-match the
    two different `select(...)` statements themselves."""

    def __init__(self, run: SimulationRunModel, completed_count: int = 0) -> None:
        self._run = run
        self._completed_count = completed_count
        self._calls = 0

    async def scalar(self, _stmt):
        self._calls += 1
        return self._run if self._calls == 1 else self._completed_count

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
    service = SimulationRunService(_FakeSession(run, completed_count=3))

    result = await service.finalize_run(run.id)

    assert result.status == "CANCELLED"
    assert result.completed_at is not None


async def test_finalize_run_sets_completed_when_a_participant_succeeded():
    run = _run("RUNNING")
    service = SimulationRunService(_FakeSession(run, completed_count=1))

    result = await service.finalize_run(run.id)

    assert result.status == "COMPLETED"


async def test_finalize_run_sets_failed_when_no_participant_succeeded():
    run = _run("RUNNING")
    service = SimulationRunService(_FakeSession(run, completed_count=0))

    result = await service.finalize_run(run.id)

    assert result.status == "FAILED"
