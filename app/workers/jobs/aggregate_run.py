from sqlalchemy.ext.asyncio import AsyncSession


async def handle_aggregate_run(session: AsyncSession, payload: dict) -> None:
    """Analytics Engine (planning/09-analytics-engine.md) isn't implemented yet.
    This stub exists so the job the Study Orchestrator enqueues once every
    participant is terminal (planning/06-study-orchestrator.md item 4) is
    claimed, attempted, retried, and permanently failed through the same
    generic runner path as every other unimplemented job type, instead of
    silently vanishing. `simulation_runs.status` is already COMPLETED/FAILED
    by the time this runs (`SimulationRunService.finalize_run`) — this job's
    eventual real implementation adds `metrics`/`segment_results` on top of
    that, it doesn't gate the status itself."""
    raise NotImplementedError(
        f"aggregate_run: Analytics Engine not implemented yet "
        f"(simulation_run_id={payload.get('simulation_run_id')})"
    )
