import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models import HumanBenchmarkModel


class BenchmarkService:
    """Owns the `human_benchmarks` table only — no ownership check (that's
    StudyService, composed in app/usecases/benchmark.py:BenchmarkUseCase). No
    minimum-field validation here either: 04-Evaluation-Spec §2's per-metric
    requirements are the Validation Engine's concern when it reads this, not a
    gate on upload."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        study_id: uuid.UUID,
        source: str | None,
        task_outcomes: dict | None,
        interaction_rates: dict | None,
        segment_labels: dict | None,
        attention_data: dict | None,
    ) -> HumanBenchmarkModel:
        existing = await self.get_latest_for_study_or_none(study_id)
        benchmark = HumanBenchmarkModel(
            study_id=study_id,
            source=source,
            task_outcomes=task_outcomes,
            interaction_rates=interaction_rates,
            segment_labels=segment_labels,
            attention_data=attention_data,
            version=(existing.version + 1) if existing else 1,
        )
        self._session.add(benchmark)
        await self._session.flush()
        return benchmark

    async def get_latest_for_study_or_none(self, study_id: uuid.UUID) -> HumanBenchmarkModel | None:
        return await self._session.scalar(
            select(HumanBenchmarkModel)
            .where(HumanBenchmarkModel.study_id == study_id)
            .order_by(HumanBenchmarkModel.version.desc())
        )

    async def get_latest_for_study(self, study_id: uuid.UUID) -> HumanBenchmarkModel:
        benchmark = await self.get_latest_for_study_or_none(study_id)
        if benchmark is None:
            raise NotFoundError(f"No human benchmark uploaded for study {study_id}")
        return benchmark
