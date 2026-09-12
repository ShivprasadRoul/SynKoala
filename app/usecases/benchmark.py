import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HumanBenchmarkModel, UserModel
from app.services.benchmark_service import BenchmarkService
from app.services.study_service import StudyService


class BenchmarkUseCase:
    """Orchestration for the Human Benchmark resource (planning/02-api.md).
    Composes StudyService (ownership) + BenchmarkService (persistence)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._studies = StudyService(session)
        self._benchmarks = BenchmarkService(session)

    async def upsert(
        self,
        user: UserModel,
        study_id: uuid.UUID,
        source: str | None,
        task_outcomes: dict | None,
        interaction_rates: dict | None,
        segment_labels: dict | None,
        attention_data: dict | None,
    ) -> HumanBenchmarkModel:
        await self._studies.get_owned(user, study_id)
        benchmark = await self._benchmarks.upsert(
            study_id, source, task_outcomes, interaction_rates, segment_labels, attention_data
        )
        await self._session.commit()
        return benchmark

    async def get(self, user: UserModel, study_id: uuid.UUID) -> HumanBenchmarkModel:
        await self._studies.get_owned(user, study_id)
        return await self._benchmarks.get_latest_for_study(study_id)
