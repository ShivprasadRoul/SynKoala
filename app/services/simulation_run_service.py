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
        self,
        study_id: uuid.UUID,
        population_size: int,
        config: dict | None,
        seed: int | None,
        task_id: uuid.UUID | None = None,
        source: str = "SYNTHETIC",
    ) -> SimulationRunModel:
        run = SimulationRunModel(
            study_id=study_id,
            task_id=task_id,
            population_size=population_size,
            status="RUNNING",
            config=config,
            seed=seed,
            source=source,
            started_at=datetime.now(UTC),
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def create_participant_run(
        self,
        run_id: uuid.UUID,
        participant_id: uuid.UUID | None = None,
        tester_label: str | None = None,
    ) -> ParticipantRunModel:
        # participant_id is None for a human tester's session
        # (planning/13-journey-capture.md) — every synthetic caller still passes one.
        participant_run = ParticipantRunModel(
            simulation_run_id=run_id,
            participant_id=participant_id,
            tester_label=tester_label,
            status="PENDING" if participant_id is not None else "IN_PROGRESS",
            started_at=None if participant_id is not None else datetime.now(UTC),
        )
        self._session.add(participant_run)
        await self._session.flush()
        return participant_run

    async def increment_population_size(self, run: SimulationRunModel) -> SimulationRunModel:
        run.population_size += 1
        await self._session.flush()
        return run

    async def complete_participant_run(
        self,
        participant_run: ParticipantRunModel,
        status: str,
        final_outcome: dict | None,
        current_screen_id: uuid.UUID | None = None,
    ) -> ParticipantRunModel:
        participant_run.status = status
        participant_run.final_outcome = final_outcome
        participant_run.completed_at = datetime.now(UTC)
        if current_screen_id is not None:
            participant_run.current_screen_id = current_screen_id
        await self._session.flush()
        return participant_run

    async def set_voice_note_url(
        self, participant_run: ParticipantRunModel, voice_note_url: str
    ) -> ParticipantRunModel:
        participant_run.voice_note_url = voice_note_url
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

    async def list_sibling_runs(
        self, study_id: uuid.UUID, task_id: uuid.UUID | None, exclude_run_id: uuid.UUID
    ) -> list[SimulationRunModel]:
        """Completed `SYNTHETIC` runs of the same study+task, other than the one
        being validated — the Validation Engine (planning/10) buckets these by
        `config["participant_model"]` in Python (not a JSONB filter here) to
        find baseline runs (a specific participant model) and stability
        siblings (repeats of the same model with different seeds)."""
        stmt = select(SimulationRunModel).where(
            SimulationRunModel.study_id == study_id,
            SimulationRunModel.status == "COMPLETED",
            SimulationRunModel.source == "SYNTHETIC",
            SimulationRunModel.id != exclude_run_id,
        )
        if task_id is not None:
            stmt = stmt.where(SimulationRunModel.task_id == task_id)
        result = await self._session.scalars(stmt.order_by(SimulationRunModel.created_at.desc()))
        return list(result)

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
