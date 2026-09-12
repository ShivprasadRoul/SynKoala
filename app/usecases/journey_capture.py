import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import LifecycleError, NotFoundError
from app.db.models import (
    ObservationModel,
    ParticipantRunModel,
    SimulationRunModel,
    TaskModel,
    UserModel,
)
from app.services.journey_capture_service import JourneyCaptureService
from app.services.simulation_run_service import SimulationRunService
from app.services.study_service import StudyService
from app.services.task_service import TaskService


class JourneyCaptureUseCase:
    """Orchestration for planning/13-journey-capture.md. Composes StudyService
    (ownership), TaskService (intended_path), the existing SimulationRunService
    (human runs/participant runs, reused unchanged per the module's "extend, don't
    parallel-build" design decision), and JourneyCaptureService (capture-token
    issuance, observations, voice-note upload)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._studies = StudyService(session)
        self._tasks = TaskService(session)
        self._runs = SimulationRunService(session)
        self._capture = JourneyCaptureService(session)

    async def _resolve_task(
        self, user: UserModel, study_id: uuid.UUID, task_id: uuid.UUID
    ) -> TaskModel:
        await self._studies.get_owned(user, study_id)
        task = await self._tasks.get_by_id(task_id)
        if task.study_id != study_id:
            raise NotFoundError(f"Task {task_id} not found for study {study_id}")
        return task

    async def set_intended_path(
        self, user: UserModel, study_id: uuid.UUID, task_id: uuid.UUID, steps: list[dict]
    ) -> TaskModel:
        task = await self._resolve_task(user, study_id, task_id)
        task = await self._tasks.set_intended_path(task, steps)
        await self._session.commit()
        return task

    async def get_intended_path(
        self, user: UserModel, study_id: uuid.UUID, task_id: uuid.UUID
    ) -> list[dict]:
        task = await self._resolve_task(user, study_id, task_id)
        if not task.intended_path:
            raise NotFoundError(f"No intended path captured yet for task {task_id}")
        return task.intended_path

    async def create_human_run(
        self, user: UserModel, study_id: uuid.UUID, task_id: uuid.UUID
    ) -> SimulationRunModel:
        task = await self._resolve_task(user, study_id, task_id)
        run = await self._runs.create_run(
            study_id, population_size=0, config=None, seed=None, task_id=task.id, source="HUMAN"
        )
        await self._session.commit()
        return run

    async def create_session(
        self, user: UserModel, run_id: uuid.UUID, tester_label: str | None
    ) -> tuple[ParticipantRunModel, str]:
        run = await self._runs.get_by_id(run_id)
        await self._studies.get_owned(user, run.study_id)  # ownership check
        if run.source != "HUMAN":
            raise LifecycleError(f"Simulation run {run_id} is not a human run")
        participant_run = await self._runs.create_participant_run(
            run.id, participant_id=None, tester_label=tester_label
        )
        await self._runs.increment_population_size(run)
        token = self._capture.issue_capture_token(participant_run.id)
        await self._session.commit()
        return participant_run, token

    async def record_observation(
        self,
        participant_run: ParticipantRunModel,
        sequence_no: int,
        obs_type: str,
        screen_figma_node_id: str | None,
        element_figma_node_id: str | None,
        x: float | None,
        y: float | None,
        duration_ms: int | None,
        payload: dict | None,
    ) -> ObservationModel:
        observation = await self._capture.record_observation(
            participant_run.id,
            sequence_no,
            obs_type,
            screen_figma_node_id,
            element_figma_node_id,
            x,
            y,
            duration_ms,
            payload,
        )
        await self._session.commit()
        return observation

    async def set_voice_note(
        self, participant_run: ParticipantRunModel, file_bytes: bytes, content_type: str
    ) -> ParticipantRunModel:
        voice_note_url = await self._capture.upload_voice_note(
            participant_run.id, file_bytes, content_type
        )
        participant_run = await self._runs.set_voice_note_url(participant_run, voice_note_url)
        await self._session.commit()
        return participant_run

    async def complete_session(
        self, participant_run: ParticipantRunModel, status: str, final_outcome: dict | None
    ) -> ParticipantRunModel:
        participant_run = await self._runs.complete_participant_run(
            participant_run, status, final_outcome
        )
        if await self._runs.is_run_complete(participant_run.simulation_run_id):
            await self._runs.finalize_run(participant_run.simulation_run_id)
        await self._session.commit()
        return participant_run
