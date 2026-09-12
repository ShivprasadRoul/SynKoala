import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models import ParticipantRunModel, SimulationRunModel


class SimulationRunService:
    """Owns the `simulation_runs`/`participant_runs` tables only — no ownership
    check, no task/audience/job logic (that's SimulationUseCase, composed in
    app/usecases/simulations.py)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_run(
        self, study_id: uuid.UUID, population_size: int, config: dict | None, seed: int | None
    ) -> SimulationRunModel:
        run = SimulationRunModel(
            study_id=study_id,
            population_size=population_size,
            status="RUNNING",
            config=config,
            seed=seed,
            started_at=datetime.now(UTC),
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def create_participant_run(
        self, run_id: uuid.UUID, participant_id: uuid.UUID
    ) -> ParticipantRunModel:
        participant_run = ParticipantRunModel(
            simulation_run_id=run_id, participant_id=participant_id, status="PENDING"
        )
        self._session.add(participant_run)
        await self._session.flush()
        return participant_run

    async def get_by_id(self, run_id: uuid.UUID) -> SimulationRunModel:
        run = await self._session.scalar(
            select(SimulationRunModel).where(SimulationRunModel.id == run_id)
        )
        if run is None:
            raise NotFoundError(f"Simulation run {run_id} not found")
        return run

    async def mark_cancelling(self, run: SimulationRunModel) -> SimulationRunModel:
        run.status = "CANCELLING"
        await self._session.flush()
        return run

    async def get_participant_run(self, participant_run_id: uuid.UUID) -> ParticipantRunModel:
        participant_run = await self._session.get(ParticipantRunModel, participant_run_id)
        if participant_run is None:
            raise NotFoundError(f"Participant run {participant_run_id} not found")
        return participant_run

    async def is_run_complete(self, run_id: uuid.UUID) -> bool:
        total = await self.count_total(run_id)
        terminal = await self.count_terminal(run_id)
        return total > 0 and terminal == total

    async def finalize_run(self, run_id: uuid.UUID) -> SimulationRunModel:
        """Called once every participant_run for a run has reached a terminal
        status — planning/06-study-orchestrator.md's aggregation trigger, minus
        the actual aggregation (planning/09), which hasn't landed yet."""
        run = await self.get_by_id(run_id)
        succeeded = await self._session.scalar(
            select(func.count())
            .select_from(ParticipantRunModel)
            .where(
                ParticipantRunModel.simulation_run_id == run_id,
                ParticipantRunModel.status == "COMPLETED",
            )
        )
        run.status = "COMPLETED" if succeeded else "FAILED"
        run.completed_at = datetime.now(UTC)
        await self._session.flush()
        return run

    async def count_total(self, run_id: uuid.UUID) -> int:
        total = await self._session.scalar(
            select(func.count())
            .select_from(ParticipantRunModel)
            .where(ParticipantRunModel.simulation_run_id == run_id)
        )
        return total or 0

    async def count_terminal(self, run_id: uuid.UUID) -> int:
        completed = await self._session.scalar(
            select(func.count())
            .select_from(ParticipantRunModel)
            .where(
                ParticipantRunModel.simulation_run_id == run_id,
                ParticipantRunModel.status.in_(("COMPLETED", "FAILED", "ABANDONED")),
            )
        )
        return completed or 0
