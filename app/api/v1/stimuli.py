import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.routes import StimuliRoutes
from app.core.auth import get_current_user
from app.core.storage import StorageError, signed_url_or_none
from app.db.models import UserModel
from app.db.session import get_session
from app.domain.schemas.stimulus import AnalyzeJobRead, StimulusRead
from app.usecases.stimulus import StimulusUseCase

logger = logging.getLogger(__name__)

stimuli_router_v1 = APIRouter(tags=StimuliRoutes.TAGS)


async def _sign_or_none(image_url: str | None) -> str | None:
    """A Storage hiccup while signing must degrade that one screen to "no
    preview" (the frontend already handles a null `image_url`), not 500 the
    whole list/create response — especially since the *previous* behavior
    (returning the raw, always-broken internal key) never raised at all."""
    try:
        return await signed_url_or_none(image_url)
    except StorageError:
        logger.warning("failed to sign image_url=%r", image_url, exc_info=True)
        return None


async def _sign_screen_urls(stimuli: list[StimulusRead]) -> None:
    """`screens.image_url` is stored as the internal `"{bucket}/{path}"` key
    `download_object` needs (planning/05's VisionProvider reads it that way)
    — never a URL a browser can load directly, since the `stimuli` bucket is
    private. Swaps in a real, temporary signed URL only in the API response,
    leaving the DB value (and every other internal caller) untouched. Signs
    every screen across every stimulus in one batch rather than one at a
    time, since `list_stimuli` can return many."""
    screens = [screen for stimulus in stimuli for screen in stimulus.screens]
    signed = await asyncio.gather(*(_sign_or_none(s.image_url) for s in screens))
    for screen, url in zip(screens, signed, strict=True):
        screen.image_url = url


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
        file.filename if file is not None else None,
    )
    stimulus_read = StimulusRead.model_validate(stimulus)
    await _sign_screen_urls([stimulus_read])
    return stimulus_read


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
    reads = [StimulusRead.model_validate(s) for s in stimuli]
    await _sign_screen_urls(reads)
    return reads
