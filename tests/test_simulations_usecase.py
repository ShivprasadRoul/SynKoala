import uuid
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.errors import LifecycleError
from app.db.models import ParticipantRecordModel, StudyModel, TaskModel
from app.usecases.simulations import SimulationUseCase


class _NoOpSession:
    async def commit(self) -> None:
        pass


def _ready_study() -> StudyModel:
    return StudyModel(id=uuid.uuid4(), project_id=uuid.uuid4(), name="Study", status="READY")


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
