import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models import TaskModel


class TaskService:
    """Owns the `tasks` table only — no ownership check (that's StudyService,
    composed in app/usecases/tasks.py:TaskUseCase). `expected_critical_actions` is
    the Critical User Task addition from 01-PRD-Synthetic-Koala.md §6."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        study_id: uuid.UUID,
        instruction: str,
        starting_point: str | None,
        success_conditions: dict | None,
        constraints: dict | None,
        expected_critical_actions: list[str] | None,
    ) -> TaskModel:
        task = TaskModel(
            study_id=study_id,
            instruction=instruction,
            starting_point=starting_point,
            success_conditions=success_conditions,
            constraints=constraints,
            expected_critical_actions=expected_critical_actions,
        )
        self._session.add(task)
        await self._session.flush()
        return task

    async def list_for_study(self, study_id: uuid.UUID) -> list[TaskModel]:
        result = await self._session.scalars(
            select(TaskModel).where(TaskModel.study_id == study_id).order_by(TaskModel.created_at)
        )
        return list(result)

    async def get_by_id(self, task_id: uuid.UUID) -> TaskModel:
        task = await self._session.scalar(select(TaskModel).where(TaskModel.id == task_id))
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")
        return task

    async def update(
        self,
        task: TaskModel,
        *,
        instruction: str | None = None,
        starting_point: str | None = None,
        success_conditions: dict | None = None,
        constraints: dict | None = None,
        expected_critical_actions: list[str] | None = None,
    ) -> TaskModel:
        if instruction is not None:
            task.instruction = instruction
        if starting_point is not None:
            task.starting_point = starting_point
        if success_conditions is not None:
            task.success_conditions = success_conditions
        if constraints is not None:
            task.constraints = constraints
        if expected_critical_actions is not None:
            task.expected_critical_actions = expected_critical_actions
        await self._session.flush()
        return task
