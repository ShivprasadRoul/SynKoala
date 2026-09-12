import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import LifecycleError, NotFoundError
from app.db.models import ParticipantRecordModel, SimulationRunModel, TaskModel, UserModel
from app.services.audience_service import AudienceService
from app.services.job_service import JobService
from app.services.simulation_run_service import SimulationRunService
from app.services.stimulus_service import StimulusService
from app.services.study_service import StudyService
from app.services.task_service import TaskService


class SimulationUseCase:
    """Orchestration for the Simulation resource (planning/02-api.md /
    planning/06-study-orchestrator.md). Composes StudyService, TaskService,
    AudienceService, StimulusService, SimulationRunService, and JobService —
    fans out one simulate_participant job per participant (LLD §19)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._studies = StudyService(session)
        self._tasks = TaskService(session)
        self._audiences = AudienceService(session)
        self._stimuli = StimulusService(session)
        self._runs = SimulationRunService(session)
        self._jobs = JobService(session)

    async def _resolve_task(self, study_id: uuid.UUID, task_id: uuid.UUID | None) -> TaskModel:
        if task_id is not None:
            task = await self._tasks.get_by_id(task_id)
            if task.study_id != study_id:
                raise NotFoundError(f"Task {task_id} not found for study {study_id}")
            return task
        tasks = await self._tasks.list_for_study(study_id)
        if len(tasks) == 1:
            return tasks[0]
        if not tasks:
            raise LifecycleError(f"Study {study_id} has no task defined")
        raise LifecycleError(f"Study {study_id} has multiple tasks — specify task_id")

    async def _resolve_participants(self, study_id: uuid.UUID) -> list[ParticipantRecordModel]:
        audience = await self._audiences.get_latest_for_study(study_id)
        participants = await self._audiences.list_participants(audience.id)
        if not participants:
            raise LifecycleError(f"Study {study_id}'s audience has no generated participants")
        return participants

    async def create_run(
        self,
        user: UserModel,
        study_id: uuid.UUID,
        population_size: int,
        task_id: uuid.UUID | None,
        config: dict | None,
        seed: int | None,
    ) -> SimulationRunModel:
        study = await self._studies.get_owned(user, study_id)
        if study.status != "READY":
            raise LifecycleError(
                f"Study {study_id} must be READY before a simulation can be started "
                f"(currently {study.status})"
            )
        if not await self._stimuli.has_analyzed_screens(study_id):
            raise LifecycleError(
                f"Study {study_id} has no analyzed stimulus yet — "
                "run POST /studies/:id/stimulus/analyze first"
            )
        task = await self._resolve_task(study_id, task_id)
        participants = await self._resolve_participants(study_id)
        if population_size > len(participants):
            raise LifecycleError(
                f"Requested {population_size} participants but only "
                f"{len(participants)} were generated"
            )
        selected = participants[:population_size]

        run = await self._runs.create_run(study_id, population_size, config, seed)

        for participant in selected:
            participant_run = await self._runs.create_participant_run(run.id, participant.id)
            await self._jobs.enqueue(
                "simulate_participant",
                {
                    "simulation_run_id": str(run.id),
                    "participant_run_id": str(participant_run.id),
                    "participant_id": str(participant.id),
                    "study_id": str(study_id),
                    "task_id": str(task.id),
                    "seed": seed,
                },
            )

        await self._studies.update(study, status="RUNNING")
        await self._session.commit()
        return run

    async def get_run(self, user: UserModel, run_id: uuid.UUID) -> SimulationRunModel:
        run = await self._runs.get_by_id(run_id)
        await self._studies.get_owned(user, run.study_id)  # ownership check
        return run

    async def cancel_run(self, user: UserModel, run_id: uuid.UUID) -> SimulationRunModel:
        run = await self.get_run(user, run_id)
        if run.status in ("COMPLETED", "FAILED", "CANCELLED"):
            raise LifecycleError(f"Cannot cancel a run in status {run.status}")
        run = await self._runs.mark_cancelling(run)
        await self._jobs.cancel_pending("simulate_participant", "simulation_run_id", str(run_id))
        await self._session.commit()
        return run

    async def get_progress(self, user: UserModel, run_id: uuid.UUID) -> dict:
        run = await self.get_run(user, run_id)
        total = await self._runs.count_total(run_id)
        completed = await self._runs.count_terminal(run_id)
        return {"status": run.status, "completed": completed, "total": total}
