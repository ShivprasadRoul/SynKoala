import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.routes import TasksRoutes
from app.core.auth import get_current_user
from app.db.models import UserModel
from app.db.session import get_session
from app.domain.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.usecases.tasks import TaskUseCase

tasks_router_v1 = APIRouter(tags=TasksRoutes.TAGS)


@tasks_router_v1.post(
    TasksRoutes.LIST_CREATE, response_model=TaskRead, status_code=status.HTTP_201_CREATED
)
async def create_task(
    study_id: uuid.UUID,
    body: TaskCreate,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TaskRead:
    use_case = TaskUseCase(session)
    task = await use_case.create(
        current_user,
        study_id,
        body.instruction,
        body.starting_point,
        body.success_conditions,
        body.constraints,
        body.expected_critical_actions,
    )
    return TaskRead.model_validate(task)


@tasks_router_v1.get(TasksRoutes.LIST_CREATE, response_model=list[TaskRead])
async def list_tasks(
    study_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TaskRead]:
    use_case = TaskUseCase(session)
    tasks = await use_case.list_tasks(current_user, study_id)
    return [TaskRead.model_validate(t) for t in tasks]


@tasks_router_v1.patch(TasksRoutes.UPDATE, response_model=TaskRead)
async def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TaskRead:
    use_case = TaskUseCase(session)
    task = await use_case.update(
        current_user,
        task_id,
        instruction=body.instruction,
        starting_point=body.starting_point,
        success_conditions=body.success_conditions,
        constraints=body.constraints,
        expected_critical_actions=body.expected_critical_actions,
    )
    return TaskRead.model_validate(task)
