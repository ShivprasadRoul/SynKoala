import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.routes import AudiencesRoutes
from app.core.auth import get_current_user
from app.db.models import UserModel
from app.db.session import get_session
from app.domain.schemas.audience import (
    AudienceCreate,
    AudienceRead,
    GenerateAudienceRequest,
    ParticipantRead,
)
from app.usecases.audiences import AudienceUseCase

audiences_router_v1 = APIRouter(tags=AudiencesRoutes.TAGS)


@audiences_router_v1.post(
    AudiencesRoutes.LIST_CREATE, response_model=AudienceRead, status_code=status.HTTP_201_CREATED
)
async def create_audience(
    study_id: uuid.UUID,
    body: AudienceCreate,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AudienceRead:
    use_case = AudienceUseCase(session)
    audience = await use_case.create(current_user, study_id, body.name, body.definition)
    return AudienceRead.model_validate(audience)


@audiences_router_v1.get(AudiencesRoutes.LIST_CREATE, response_model=AudienceRead)
async def get_audience(
    study_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AudienceRead:
    use_case = AudienceUseCase(session)
    audience = await use_case.get(current_user, study_id)
    return AudienceRead.model_validate(audience)


@audiences_router_v1.post(AudiencesRoutes.GENERATE, response_model=list[ParticipantRead])
async def generate_population(
    study_id: uuid.UUID,
    body: GenerateAudienceRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ParticipantRead]:
    use_case = AudienceUseCase(session)
    participants = await use_case.generate_population(
        current_user, study_id, body.population_size, body.seed
    )
    return [ParticipantRead.model_validate(p) for p in participants]
