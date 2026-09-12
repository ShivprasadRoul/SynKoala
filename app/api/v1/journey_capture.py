import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.routes import JourneyCaptureRoutes
from app.core.auth import get_capture_token, get_current_user
from app.db.models import ParticipantRunModel, UserModel
from app.db.session import get_session
from app.domain.schemas.journey_capture import (
    CaptureSessionCreate,
    CaptureSessionRead,
    IntendedPathRead,
    IntendedPathSet,
    ObservationCreate,
    ObservationRead,
    ParticipantRunComplete,
    ParticipantRunRead,
)
from app.domain.schemas.simulation import SimulationRunRead
from app.domain.schemas.task import TaskRead
from app.usecases.journey_capture import JourneyCaptureUseCase

journey_capture_router_v1 = APIRouter(tags=JourneyCaptureRoutes.TAGS)


# --- Creator-authenticated: defined path + human-run/session setup ---------------


@journey_capture_router_v1.post(JourneyCaptureRoutes.INTENDED_PATH, response_model=TaskRead)
async def set_intended_path(
    study_id: uuid.UUID,
    task_id: uuid.UUID,
    body: IntendedPathSet,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TaskRead:
    use_case = JourneyCaptureUseCase(session)
    task = await use_case.set_intended_path(
        current_user, study_id, task_id, [step.model_dump() for step in body.steps]
    )
    return TaskRead.model_validate(task)


@journey_capture_router_v1.get(JourneyCaptureRoutes.INTENDED_PATH, response_model=IntendedPathRead)
async def get_intended_path(
    study_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IntendedPathRead:
    use_case = JourneyCaptureUseCase(session)
    steps = await use_case.get_intended_path(current_user, study_id, task_id)
    return IntendedPathRead(steps=steps)


@journey_capture_router_v1.post(
    JourneyCaptureRoutes.HUMAN_RUNS,
    response_model=SimulationRunRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_human_run(
    study_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SimulationRunRead:
    use_case = JourneyCaptureUseCase(session)
    run = await use_case.create_human_run(current_user, study_id, task_id)
    return SimulationRunRead.model_validate(run)


@journey_capture_router_v1.post(
    JourneyCaptureRoutes.SESSIONS,
    response_model=CaptureSessionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_capture_session(
    run_id: uuid.UUID,
    body: CaptureSessionCreate,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CaptureSessionRead:
    use_case = JourneyCaptureUseCase(session)
    participant_run, token = await use_case.create_session(current_user, run_id, body.tester_label)
    return CaptureSessionRead(participant_run_id=participant_run.id, capture_token=token)


# --- Capture-token-authenticated: live capture from the mobile app ---------------


@journey_capture_router_v1.post(
    JourneyCaptureRoutes.OBSERVATIONS,
    response_model=ObservationRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_observation(
    participant_run_id: uuid.UUID,
    body: ObservationCreate,
    participant_run: ParticipantRunModel = Depends(get_capture_token),
    session: AsyncSession = Depends(get_session),
) -> ObservationRead:
    # participant_run comes from the verified token, not the URL param above — a
    # token can never be used to write into a different session even if the URL
    # is guessed (planning/13-journey-capture.md).
    use_case = JourneyCaptureUseCase(session)
    observation = await use_case.record_observation(
        participant_run,
        body.sequence_no,
        body.type,
        body.screen_figma_node_id,
        body.element_figma_node_id,
        body.x,
        body.y,
        body.duration_ms,
        body.payload,
    )
    return ObservationRead(id=observation.id)


@journey_capture_router_v1.post(JourneyCaptureRoutes.VOICE_NOTE, response_model=ParticipantRunRead)
async def upload_voice_note(
    participant_run_id: uuid.UUID,
    file: UploadFile = File(...),
    participant_run: ParticipantRunModel = Depends(get_capture_token),
    session: AsyncSession = Depends(get_session),
) -> ParticipantRunRead:
    use_case = JourneyCaptureUseCase(session)
    file_bytes = await file.read()
    participant_run = await use_case.set_voice_note(
        participant_run, file_bytes, file.content_type or "application/octet-stream"
    )
    return ParticipantRunRead.model_validate(participant_run)


@journey_capture_router_v1.post(JourneyCaptureRoutes.COMPLETE, response_model=ParticipantRunRead)
async def complete_capture_session(
    participant_run_id: uuid.UUID,
    body: ParticipantRunComplete,
    participant_run: ParticipantRunModel = Depends(get_capture_token),
    session: AsyncSession = Depends(get_session),
) -> ParticipantRunRead:
    use_case = JourneyCaptureUseCase(session)
    participant_run = await use_case.complete_session(
        participant_run, body.status, body.final_outcome
    )
    return ParticipantRunRead.model_validate(participant_run)
