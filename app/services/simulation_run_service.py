import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
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

    async def lock_for_finalize(self, run_id: uuid.UUID) -> SimulationRunModel:
        """`SELECT ... FOR UPDATE` on the run row, held for the rest of the
        caller's transaction — closes a real race in `_finalize_run_and_notify`
        (app/workers/jobs/simulate_participant.py): with `NUM_WORKERS` participant
        jobs finishing concurrently, each in its own session/transaction, the last
        two participants to go terminal can both run `is_run_complete` before
        either's own terminal write has committed, so both see "not yet complete"
        and neither ever calls `finalize_run` — the run is stuck at RUNNING
        forever despite every participant being terminal (reproduced directly:
        two 5-participant runs with NUM_WORKERS=5 both stuck this way).
        Acquiring this lock first forces concurrent finalize attempts to
        serialize: whichever job's transaction commits (releasing the lock)
        first, the next job's `is_run_complete` recheck — a fresh statement
        under READ COMMITTED — is guaranteed to see that committed write."""
        run = await self._session.scalar(
            select(SimulationRunModel).where(SimulationRunModel.id == run_id).with_for_update()
        )
        if run is None:
            raise NotFoundError(f"Simulation run {run_id} not found")
        return run

    async def mark_cancelling(self, run: SimulationRunModel) -> SimulationRunModel:
        run.status = "CANCELLING"
        await self._session.flush()
        return run

    async def abandon_pending_participant_runs(self, run_id: uuid.UUID) -> None:
        """Closes the gap `SimulationUseCase.cancel_run` used to leave open:
        `JobService.cancel_pending` flips a still-queued `simulate_participant`
        job straight to CANCELLED, so it's never claimed and never reaches
        `complete_participant_run` — without this, that job's `participant_runs`
        row would stay PENDING forever, and `is_run_complete`/`finalize_run`
        could never see the run as done. Only PENDING rows are touched here —
        an IN_PROGRESS one has a job a worker already claimed and is actively
        running; it finishes and records its own real outcome normally,
        cancel or not."""
        await self._session.execute(
            update(ParticipantRunModel)
            .where(
                ParticipantRunModel.simulation_run_id == run_id,
                ParticipantRunModel.status == "PENDING",
            )
            .values(
                status="ABANDONED",
                final_outcome={"reason": "run_cancelled"},
                completed_at=datetime.now(UTC),
            )
        )
        await self._session.flush()

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
        the actual aggregation (planning/09), which hasn't landed yet.

        A run already `CANCELLING` always finalizes to `CANCELLED`, regardless
        of how individual participants happened to end up — some may have
        completed successfully before the cancel reached them (their own job
        was already IN_PROGRESS and ran to completion), but the researcher
        explicitly asked to cancel, so the run itself must not silently become
        COMPLETED/FAILED as if nothing was cancelled.

        Otherwise `FAILED` means the *simulation* failed, not that the synthetic
        users did: a population that all abandoned is a valid result (a 100%
        drop-off is often the finding), so the run only fails when no
        participant produced a simulated outcome at all — i.e. every
        participant_run carries the `job_permanently_failed` error marker
        written by `simulate_participant`'s permanent-failure path."""
        run = await self.get_by_id(run_id)
        if run.status == "CANCELLING":
            run.status = "CANCELLED"
        else:
            errored = await self._session.scalar(
                select(func.count())
                .select_from(ParticipantRunModel)
                .where(
                    ParticipantRunModel.simulation_run_id == run_id,
                    ParticipantRunModel.final_outcome["error"].astext.isnot(None),
                )
            )
            total = await self.count_total(run_id)
            run.status = "FAILED" if total == 0 or errored == total else "COMPLETED"
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

    async def list_by_study(self, study_id: uuid.UUID) -> list[SimulationRunModel]:
        """Every run ever created for a study, oldest first — a study's run
        history (planning/02-api.md's `GET /studies/:id/simulations`). Runs are
        append-only (`create_run` always inserts, never updates a prior row),
        so this list is also each run's permanent "Run #N" position, oldest ==
        #1, without needing a dedicated sequence column."""
        result = await self._session.scalars(
            select(SimulationRunModel)
            .where(SimulationRunModel.study_id == study_id)
            .order_by(SimulationRunModel.created_at.asc())
        )
        return list(result)

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
