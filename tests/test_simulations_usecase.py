import uuid
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.errors import LifecycleError
from app.db.models import ParticipantRecordModel, StudyModel, TaskModel
from app.usecases.simulations import SimulationUseCase


class _NoOpSession:
    async def commit(self) -> None:
        pass


def _ready_study(status: str = "READY") -> StudyModel:
    return StudyModel(id=uuid.uuid4(), project_id=uuid.uuid4(), name="Study", status=status)


def _use_case_with_ready_study(study: StudyModel) -> SimulationUseCase:
    use_case = SimulationUseCase(_NoOpSession())
    use_case._studies = AsyncMock()
    use_case._studies.get_owned.return_value = study
    use_case._stimuli = AsyncMock()
    use_case._tasks = AsyncMock()
    use_case._audiences = AsyncMock()
    use_case._runs = AsyncMock()
    use_case._jobs = AsyncMock()
    return use_case


async def test_create_run_rejects_study_with_no_analyzed_stimulus():
    study = _ready_study()
    use_case = _use_case_with_ready_study(study)
    use_case._stimuli.has_analyzed_screens.return_value = False

    with pytest.raises(LifecycleError, match="no analyzed stimulus"):
        await use_case.create_run(
            user=Mock(), study_id=study.id, population_size=1, task_id=None, config=None, seed=None
        )

    use_case._tasks.list_for_study.assert_not_awaited()
    use_case._runs.create_run.assert_not_awaited()


async def test_create_run_proceeds_once_stimulus_is_analyzed():
    study = _ready_study()
    task = TaskModel(id=uuid.uuid4(), study_id=study.id, instruction="Do the thing")
    participant = ParticipantRecordModel(id=uuid.uuid4(), audience_id=uuid.uuid4(), traits={})

    use_case = _use_case_with_ready_study(study)
    use_case._stimuli.has_analyzed_screens.return_value = True
    use_case._tasks.list_for_study.return_value = [task]
    use_case._audiences.get_latest_for_study.return_value = Mock(id=uuid.uuid4())
    use_case._audiences.list_participants.return_value = [participant]
    fake_run = Mock(id=uuid.uuid4())
    use_case._runs.create_run.return_value = fake_run
    use_case._runs.create_participant_run.return_value = Mock(id=uuid.uuid4())

    result = await use_case.create_run(
        user=Mock(), study_id=study.id, population_size=1, task_id=None, config=None, seed=42
    )

    assert result is fake_run
    use_case._jobs.enqueue.assert_awaited_once()
    job_type, job_payload = use_case._jobs.enqueue.await_args.args
    assert job_type == "simulate_participant"
    assert job_payload["seed"] == 42


@pytest.mark.parametrize("status", ["RUNNING", "COMPLETED"])
async def test_create_run_allows_a_second_run_once_the_study_has_already_run_one(status):
    """The bug this closes: create_run itself moves a study to RUNNING, and
    STUDY_STATUS_TRANSITIONS has no path back from RUNNING/COMPLETED to
    READY — gating a second run on `status == "READY"` made any study
    permanently one-run-only, which breaks run_stability_cv (planning/10,
    needs >= 5 repeated runs of the same study) and baseline-comparison runs
    outright."""
    study = _ready_study(status=status)
    task = TaskModel(id=uuid.uuid4(), study_id=study.id, instruction="Do the thing")
    participant = ParticipantRecordModel(id=uuid.uuid4(), audience_id=uuid.uuid4(), traits={})

    use_case = _use_case_with_ready_study(study)
    use_case._stimuli.has_analyzed_screens.return_value = True
    use_case._tasks.list_for_study.return_value = [task]
    use_case._audiences.get_latest_for_study.return_value = Mock(id=uuid.uuid4())
    use_case._audiences.list_participants.return_value = [participant]
    use_case._runs.create_run.return_value = Mock(id=uuid.uuid4())
    use_case._runs.create_participant_run.return_value = Mock(id=uuid.uuid4())

    await use_case.create_run(
        user=Mock(), study_id=study.id, population_size=1, task_id=None, config=None, seed=None
    )

    use_case._runs.create_run.assert_awaited_once()


@pytest.mark.parametrize("status", ["DRAFT", "FAILED"])
async def test_create_run_still_rejects_a_study_that_was_never_readied(status):
    study = _ready_study(status=status)
    use_case = _use_case_with_ready_study(study)

    with pytest.raises(LifecycleError, match="must be READY"):
        await use_case.create_run(
            user=Mock(), study_id=study.id, population_size=1, task_id=None, config=None, seed=None
        )

    use_case._runs.create_run.assert_not_awaited()


async def test_cancel_run_finalizes_immediately_once_no_participants_are_left_in_progress():
    """The bug this closes: a cancelled job never reaches
    complete_participant_run, so its participant_runs row would stay PENDING
    forever unless cancel_run abandons it itself — and once that was every
    remaining participant, nothing else is left running to trigger
    finalize_run later, so cancel_run must do it inline."""
    study = _ready_study()
    run = Mock(id=uuid.uuid4(), study_id=study.id, status="RUNNING")
    use_case = _use_case_with_ready_study(study)
    use_case._runs.get_by_id.return_value = run
    use_case._runs.mark_cancelling.return_value = run
    use_case._runs.is_run_complete.return_value = True
    finalized = Mock(status="CANCELLED")
    use_case._runs.finalize_run.return_value = finalized

    result = await use_case.cancel_run(user=Mock(), run_id=run.id)

    use_case._runs.mark_cancelling.assert_awaited_once_with(run)
    use_case._jobs.cancel_pending.assert_awaited_once_with(
        "simulate_participant", "simulation_run_id", str(run.id)
    )
    use_case._runs.abandon_pending_participant_runs.assert_awaited_once_with(run.id)
    use_case._runs.finalize_run.assert_awaited_once_with(run.id)
    assert result is finalized


async def test_cancel_run_leaves_finalizing_to_the_worker_when_participants_are_still_in_progress():
    study = _ready_study()
    run = Mock(id=uuid.uuid4(), study_id=study.id, status="RUNNING")
    use_case = _use_case_with_ready_study(study)
    use_case._runs.get_by_id.return_value = run
    use_case._runs.mark_cancelling.return_value = run
    use_case._runs.is_run_complete.return_value = False

    result = await use_case.cancel_run(user=Mock(), run_id=run.id)

    use_case._runs.finalize_run.assert_not_awaited()
    assert result is run


async def test_cancel_run_rejects_an_already_terminal_run():
    study = _ready_study()
    run = Mock(id=uuid.uuid4(), study_id=study.id, status="COMPLETED")
    use_case = _use_case_with_ready_study(study)
    use_case._runs.get_by_id.return_value = run

    with pytest.raises(LifecycleError, match="Cannot cancel"):
        await use_case.cancel_run(user=Mock(), run_id=run.id)

    use_case._runs.mark_cancelling.assert_not_awaited()
    use_case._runs.abandon_pending_participant_runs.assert_not_awaited()
