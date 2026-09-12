import json
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.routes import StimuliRoutes
from app.core.auth import get_current_user
from app.db.models import UserModel
from app.db.session import get_session
from app.domain.schemas.stimulus import AnalyzeJobRead, StimulusRead
from app.usecases.stimulus import StimulusUseCase

stimuli_router_v1 = APIRouter(tags=StimuliRoutes.TAGS)


@stimuli_router_v1.post(
    StimuliRoutes.LIST_CREATE, response_model=StimulusRead, status_code=status.HTTP_201_CREATED
)
async def create_stimulus(
    study_id: uuid.UUID,
    type: str = Form(...),
    source_url: str | None = Form(None),
    metadata: str | None = Form(None, description="JSON-encoded object"),
    file: UploadFile | None = File(None),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StimulusRead:
    file_bytes = await file.read() if file is not None else None
    parsed_metadata = json.loads(metadata) if metadata else None
    use_case = StimulusUseCase(session)
    stimulus = await use_case.create(
        current_user,
        study_id,
        type,
        source_url,
        file_bytes,
        file.content_type if file is not None else None,
        parsed_metadata,
    )
    return StimulusRead.model_validate(stimulus)


@stimuli_router_v1.post(
    StimuliRoutes.ANALYZE, response_model=list[AnalyzeJobRead], status_code=status.HTTP_202_ACCEPTED
)
async def analyze_stimulus(
    study_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AnalyzeJobRead]:
    use_case = StimulusUseCase(session)
    jobs = await use_case.request_analysis(current_user, study_id)
    return [AnalyzeJobRead(job_id=j.id) for j in jobs]


@stimuli_router_v1.get(StimuliRoutes.LIST_CREATE, response_model=list[StimulusRead])
async def list_stimuli(
    study_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[StimulusRead]:
    use_case = StimulusUseCase(session)
    stimuli = await use_case.list_stimuli(current_user, study_id)
    return [StimulusRead.model_validate(s) for s in stimuli]
