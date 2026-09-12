import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.routes import BenchmarkRoutes
from app.core.auth import get_current_user
from app.db.models import UserModel
from app.db.session import get_session
from app.domain.schemas.benchmark import BenchmarkRead, BenchmarkUpload
from app.usecases.benchmark import BenchmarkUseCase

benchmark_router_v1 = APIRouter(tags=BenchmarkRoutes.TAGS)


@benchmark_router_v1.post(
    BenchmarkRoutes.UPSERT_GET, response_model=BenchmarkRead, status_code=status.HTTP_201_CREATED
)
async def upload_benchmark(
    study_id: uuid.UUID,
    body: BenchmarkUpload,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BenchmarkRead:
    use_case = BenchmarkUseCase(session)
    benchmark = await use_case.upsert(
        current_user,
        study_id,
        body.source,
        body.task_outcomes,
        body.interaction_rates,
        body.segment_labels,
        body.attention_data,
    )
    return BenchmarkRead.model_validate(benchmark)


@benchmark_router_v1.get(BenchmarkRoutes.UPSERT_GET, response_model=BenchmarkRead)
async def get_benchmark(
    study_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BenchmarkRead:
    use_case = BenchmarkUseCase(session)
    benchmark = await use_case.get(current_user, study_id)
    return BenchmarkRead.model_validate(benchmark)
