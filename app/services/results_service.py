import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    HumanBenchmarkModel,
    InsightModel,
    MetricModel,
    ObservationModel,
    ParticipantRunModel,
    SegmentResultModel,
    ValidationResultModel,
)


class ResultsService:
    """Owns read-only queries over observations/metrics/segments/validation/
    insights, keyed only by `run_id` — no ownership check (that's StudyService +
    SimulationRunService, composed in app/usecases/results.py:ResultsUseCase).
    Never renders a heatmap or path from a screenshot (HLD §1's key rule) — these
    are real queries against real tables; they're empty until the Simulation/
    Analytics/Validation/InsightModel agents (planning/07, 09, 10, 11) actually run."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_participant_runs(self, run_id: uuid.UUID) -> list[ParticipantRunModel]:
        result = await self._session.scalars(
            select(ParticipantRunModel).where(ParticipantRunModel.simulation_run_id == run_id)
        )
        return list(result)

    async def list_observations(
        self, run_id: uuid.UUID, limit: int = 200, offset: int = 0
    ) -> list[ObservationModel]:
        result = await self._session.scalars(
            select(ObservationModel)
            .join(
                ParticipantRunModel, ObservationModel.participant_run_id == ParticipantRunModel.id
            )
            .where(ParticipantRunModel.simulation_run_id == run_id)
            .order_by(ObservationModel.participant_run_id, ObservationModel.sequence_no)
            .limit(limit)
            .offset(offset)
        )
        return list(result)

    async def get_metrics(self, run_id: uuid.UUID) -> dict[str, list[MetricModel]]:
        result = await self._session.scalars(
            select(MetricModel).where(MetricModel.simulation_run_id == run_id)
        )
        by_level: dict[str, list[MetricModel]] = {
            "task_success": [],
            "friction": [],
            "discoverability": [],
        }
        for metric in result:
            by_level.setdefault(metric.level, []).append(metric)
        return by_level

    async def get_heatmap(self, run_id: uuid.UUID) -> list[dict]:
        """LLD §24: aggregate stored GAZE events into spatial bins. Element-level
        binning for the MVP (per LLD §10, pixel-level isn't required)."""
        result = await self._session.execute(
            select(
                ObservationModel.screen_id,
                ObservationModel.element_id,
                func.coalesce(func.sum(ObservationModel.duration_ms), 0).label("intensity"),
                func.count().label("fixation_count"),
            )
            .join(
                ParticipantRunModel, ObservationModel.participant_run_id == ParticipantRunModel.id
            )
            .where(ParticipantRunModel.simulation_run_id == run_id, ObservationModel.type == "GAZE")
            .group_by(ObservationModel.screen_id, ObservationModel.element_id)
        )
        return [
            {
                "screen_id": row.screen_id,
                "element_id": row.element_id,
                "intensity": float(row.intensity),
                "fixation_count": row.fixation_count,
            }
            for row in result
        ]

    async def get_paths(self, run_id: uuid.UUID, sample_size: int = 20) -> list[dict]:
        """LLD §25: sample representative paths rather than rendering every one."""
        participant_runs = await self._session.scalars(
            select(ParticipantRunModel.id)
            .where(ParticipantRunModel.simulation_run_id == run_id)
            .limit(sample_size)
        )
        paths = []
        for pr_id in participant_runs:
            screens = await self._session.scalars(
                select(ObservationModel.screen_id)
                .where(
                    ObservationModel.participant_run_id == pr_id,
                    ObservationModel.type == "SCREEN_ENTER",
                )
                .order_by(ObservationModel.sequence_no)
            )
            paths.append(
                {"participant_run_id": pr_id, "screens": [s for s in screens if s is not None]}
            )
        return paths

    async def list_segment_results(self, run_id: uuid.UUID) -> list[SegmentResultModel]:
        result = await self._session.scalars(
            select(SegmentResultModel).where(SegmentResultModel.simulation_run_id == run_id)
        )
        return list(result)

    async def list_validation_results(self, run_id: uuid.UUID) -> list[ValidationResultModel]:
        result = await self._session.scalars(
            select(ValidationResultModel).where(ValidationResultModel.simulation_run_id == run_id)
        )
        return list(result)

    async def has_human_benchmark(self, study_id: uuid.UUID) -> bool:
        count = await self._session.scalar(
            select(func.count())
            .select_from(HumanBenchmarkModel)
            .where(HumanBenchmarkModel.study_id == study_id)
        )
        return bool(count)

    async def list_insights(self, run_id: uuid.UUID) -> list[InsightModel]:
        result = await self._session.scalars(
            select(InsightModel).where(InsightModel.simulation_run_id == run_id)
        )
        return list(result)
