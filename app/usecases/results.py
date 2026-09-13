import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import LifecycleError
from app.db.models import SimulationRunModel, UserModel
from app.services.audience_service import AudienceService
from app.services.results_service import ResultsService
from app.services.simulation_run_service import SimulationRunService
from app.services.study_service import StudyService


class ResultsUseCase:
    """Orchestration for the Results resource (planning/02-api.md). Every method
    resolves run ownership (SimulationRunService + StudyService) before delegating
    to ResultsService's read-only queries — the ownership check is the same shape
    for all eight endpoints, so it's factored into one private helper."""

    def __init__(self, session: AsyncSession) -> None:
        self._studies = StudyService(session)
        self._runs = SimulationRunService(session)
        self._results = ResultsService(session)
        self._audiences = AudienceService(session)

    async def _owned_run(self, user: UserModel, run_id: uuid.UUID) -> SimulationRunModel:
        run = await self._runs.get_by_id(run_id)
        await self._studies.get_owned(user, run.study_id)
        return run

    async def list_participants(self, user: UserModel, run_id: uuid.UUID) -> list:
        await self._owned_run(user, run_id)
        return await self._results.list_participant_runs(run_id)

    async def list_observations(
        self, user: UserModel, run_id: uuid.UUID, limit: int = 200, offset: int = 0
    ) -> list:
        await self._owned_run(user, run_id)
        return await self._results.list_observations(run_id, limit, offset)

    async def get_metrics(self, user: UserModel, run_id: uuid.UUID) -> dict:
        await self._owned_run(user, run_id)
        return await self._results.get_metrics(run_id)

    async def get_heatmap(self, user: UserModel, run_id: uuid.UUID) -> list[dict]:
        await self._owned_run(user, run_id)
        return await self._results.get_heatmap(run_id)

    async def get_pixel_heatmap(
        self, user: UserModel, run_id: uuid.UUID, segment: str | None = None
    ) -> list[dict]:
        run = await self._owned_run(user, run_id)
        participant_run_ids = None
        if segment is not None:
            participant_run_ids = await self._resolve_segment_participant_run_ids(run, segment)
        return await self._results.get_pixel_heatmap(
            run_id, participant_run_ids=participant_run_ids
        )

    async def _resolve_segment_participant_run_ids(
        self, run: SimulationRunModel, segment: str
    ) -> list[uuid.UUID]:
        """Same segment-naming convention as `AnalyticsEngine.compute_segments`
        (planning/09): `"<trait>_low"`/`"<trait>_high"`, split at the 0.5
        threshold. Composing `AudienceService` (traits) with `ResultsService`
        (participant_runs) is this UseCase's job — neither Service calls the
        other."""
        trait, _, bucket = segment.rpartition("_")
        if not trait or bucket not in ("low", "high"):
            raise LifecycleError(
                f"Unrecognized segment {segment!r} — expected '<trait>_low' or '<trait>_high'"
            )
        participant_runs = await self._results.list_participant_runs(run.id)
        participant_ids = [pr.participant_id for pr in participant_runs if pr.participant_id]
        participants_by_id = await self._audiences.list_by_ids(participant_ids)

        matching_ids = []
        for participant_run in participant_runs:
            participant = participants_by_id.get(participant_run.participant_id)
            if participant is None:
                continue
            value = (participant.traits or {}).get(trait, 0.5)
            if (bucket == "low" and value < 0.5) or (bucket == "high" and value >= 0.5):
                matching_ids.append(participant_run.id)
        return matching_ids

    async def get_paths(self, user: UserModel, run_id: uuid.UUID) -> list[dict]:
        await self._owned_run(user, run_id)
        return await self._results.get_paths(run_id)

    async def get_scanpaths(self, user: UserModel, run_id: uuid.UUID) -> list[dict]:
        await self._owned_run(user, run_id)
        return await self._results.get_scanpaths(run_id)

    async def list_segments(self, user: UserModel, run_id: uuid.UUID) -> list:
        await self._owned_run(user, run_id)
        return await self._results.list_segment_results(run_id)

    async def get_validation(self, user: UserModel, run_id: uuid.UUID) -> dict:
        run = await self._owned_run(user, run_id)
        results = await self._results.list_validation_results(run_id)
        if results:
            return {"status": "ok", "results": results}
        has_benchmark = await self._results.has_human_benchmark(run.study_id)
        return {"status": "ok" if has_benchmark else "no_benchmark", "results": results}

    async def list_insights(self, user: UserModel, run_id: uuid.UUID) -> list:
        await self._owned_run(user, run_id)
        return await self._results.list_insights(run_id)
