import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TaskModel, UserModel
from app.services.study_service import StudyService
from app.services.task_service import TaskService


class TaskUseCase:
    """Orchestration for the TaskModel resource (planning/02-api.md). Composes
    StudyService (ownership) + TaskService (persistence)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._studies = StudyService(session)
        self._tasks = TaskService(session)

    async def create(
        self,
        user: UserModel,
        study_id: uuid.UUID,
        instruction: str,
        starting_point: str | None,
        success_conditions: dict | None,
        constraints: dict | None,
        expected_critical_actions: list[str] | None,
    ) -> TaskModel:
        await self._studies.get_owned(user, study_id)
        task = await self._tasks.create(
            study_id,
            instruction,
            starting_point,
            success_conditions,
            constraints,
            expected_critical_actions,
        )
        await self._session.commit()
        return task

    async def list_tasks(self, user: UserModel, study_id: uuid.UUID) -> list[TaskModel]:
        await self._studies.get_owned(user, study_id)
        return await self._tasks.list_for_study(study_id)

    async def update(
        self,
        user: UserModel,
        task_id: uuid.UUID,
        *,
        instruction: str | None = None,
        starting_point: str | None = None,
        success_conditions: dict | None = None,
        constraints: dict | None = None,
        expected_critical_actions: list[str] | None = None,
    ) -> TaskModel:
        task = await self._tasks.get_by_id(task_id)
        await self._studies.get_owned(user, task.study_id)  # ownership check
        task = await self._tasks.update(
            task,
            instruction=instruction,
            starting_point=starting_point,
            success_conditions=success_conditions,
            constraints=constraints,
            expected_critical_actions=expected_critical_actions,
        )
        await self._session.commit()
        return task
