import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.routes import StudiesRoutes
from app.core.auth import get_current_user
from app.db.models import UserModel
from app.db.session import get_session
from app.domain.schemas.study import StudyCreate, StudyRead, StudyUpdate
from app.usecases.studies import StudyUseCase

studies_router_v1 = APIRouter(tags=StudiesRoutes.TAGS)


@studies_router_v1.post(
    StudiesRoutes.LIST_CREATE, response_model=StudyRead, status_code=status.HTTP_201_CREATED
)
async def create_study(
    body: StudyCreate,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StudyRead:
    use_case = StudyUseCase(session)
    study = await use_case.create(current_user, body.name, body.objective, body.population_size)
    return StudyRead.model_validate(study)


@studies_router_v1.get(StudiesRoutes.LIST_CREATE, response_model=list[StudyRead])
async def list_studies(
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[StudyRead]:
    use_case = StudyUseCase(session)
    studies = await use_case.list_studies(current_user)
    return [StudyRead.model_validate(s) for s in studies]


@studies_router_v1.get(StudiesRoutes.DETAIL, response_model=StudyRead)
async def get_study(
    study_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StudyRead:
    use_case = StudyUseCase(session)
    study = await use_case.get(current_user, study_id)
    return StudyRead.model_validate(study)


@studies_router_v1.patch(StudiesRoutes.DETAIL, response_model=StudyRead)
async def update_study(
    study_id: uuid.UUID,
    body: StudyUpdate,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StudyRead:
    use_case = StudyUseCase(session)
    study = await use_case.update(
        current_user,
        study_id,
        name=body.name,
        objective=body.objective,
        status=body.status,
        population_size=body.population_size,
    )
    return StudyRead.model_validate(study)


@studies_router_v1.delete(StudiesRoutes.DETAIL, status_code=status.HTTP_204_NO_CONTENT)
async def delete_study(
    study_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    use_case = StudyUseCase(session)
    await use_case.delete(current_user, study_id)
