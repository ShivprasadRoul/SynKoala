from sqlalchemy.ext.asyncio import AsyncSession


async def handle_analyze_stimulus(session: AsyncSession, payload: dict) -> None:
    """VisionProvider (planning/05-stimulus-engine.md) isn't implemented yet. This
    stub exists so an `analyze_stimulus` job is claimed, attempted, retried, and
    permanently failed through the same generic runner path as every other job
    type, instead of sitting PENDING forever with no record of why."""
    raise NotImplementedError(
        f"analyze_stimulus: VisionProvider not implemented yet "
        f"(stimulus_id={payload.get('stimulus_id')})"
    )
