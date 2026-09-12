import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.routes import ResultsRoutes
from app.core.auth import get_current_user
from app.db.models import UserModel
from app.db.session import get_session
from app.domain.schemas.results import (
    HeatmapCell,
    InsightRead,
    MetricRead,
    MetricsResponse,
    ObservationRead,
    ParticipantRunRead,
    PathRead,
    SegmentResultRead,
    ValidationResponse,
    ValidationResultRead,
)
from app.usecases.results import ResultsUseCase

results_router_v1 = APIRouter(tags=ResultsRoutes.TAGS)


@results_router_v1.get(ResultsRoutes.PARTICIPANTS, response_model=list[ParticipantRunRead])
async def list_participants(
    run_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ParticipantRunRead]:
    use_case = ResultsUseCase(session)
    runs = await use_case.list_participants(current_user, run_id)
    return [ParticipantRunRead.model_validate(r) for r in runs]


@results_router_v1.get(ResultsRoutes.OBSERVATIONS, response_model=list[ObservationRead])
async def list_observations(
    run_id: uuid.UUID,
    limit: int = 200,
    offset: int = 0,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ObservationRead]:
    use_case = ResultsUseCase(session)
    observations = await use_case.list_observations(current_user, run_id, limit, offset)
    return [ObservationRead.model_validate(o) for o in observations]


@results_router_v1.get(ResultsRoutes.METRICS, response_model=MetricsResponse)
async def get_metrics(
    run_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MetricsResponse:
    use_case = ResultsUseCase(session)
    by_level = await use_case.get_metrics(current_user, run_id)
    return MetricsResponse(
        task_success=[MetricRead.model_validate(m) for m in by_level["task_success"]],
        friction=[MetricRead.model_validate(m) for m in by_level["friction"]],
        discoverability=[MetricRead.model_validate(m) for m in by_level["discoverability"]],
    )


@results_router_v1.get(ResultsRoutes.HEATMAP, response_model=list[HeatmapCell])
async def get_heatmap(
    run_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[HeatmapCell]:
    use_case = ResultsUseCase(session)
    cells = await use_case.get_heatmap(current_user, run_id)
    return [HeatmapCell(**c) for c in cells]


@results_router_v1.get(ResultsRoutes.PATHS, response_model=list[PathRead])
async def get_paths(
    run_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PathRead]:
    use_case = ResultsUseCase(session)
    paths = await use_case.get_paths(current_user, run_id)
    return [PathRead(**p) for p in paths]


@results_router_v1.get(ResultsRoutes.SEGMENTS, response_model=list[SegmentResultRead])
async def get_segments(
    run_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[SegmentResultRead]:
    use_case = ResultsUseCase(session)
    segments = await use_case.list_segments(current_user, run_id)
    return [SegmentResultRead.model_validate(s) for s in segments]


@results_router_v1.get(ResultsRoutes.VALIDATION, response_model=ValidationResponse)
async def get_validation(
    run_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ValidationResponse:
    use_case = ResultsUseCase(session)
    payload = await use_case.get_validation(current_user, run_id)
    return ValidationResponse(
        status=payload["status"],
        results=[ValidationResultRead.model_validate(r) for r in payload["results"]],
    )


@results_router_v1.get(ResultsRoutes.INSIGHTS, response_model=list[InsightRead])
async def get_insights(
    run_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[InsightRead]:
    use_case = ResultsUseCase(session)
    insights = await use_case.list_insights(current_user, run_id)
    return [InsightRead.model_validate(i) for i in insights]
