import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SimulationRunModel, UserModel
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

    async def get_paths(self, user: UserModel, run_id: uuid.UUID) -> list[dict]:
        await self._owned_run(user, run_id)
        return await self._results.get_paths(run_id)

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
