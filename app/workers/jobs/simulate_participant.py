import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.simulation_run_service import SimulationRunService

_NOT_IMPLEMENTED_MESSAGE = (
    "simulate_participant: Simulation Engine loop (ORIENT->...->CHECK TASK) not "
    "implemented yet (planning/07-simulation-engine.md, 10-validation-engine.md, "
    "11-insight-engine.md)"
)


async def handle_simulate_participant(session: AsyncSession, payload: dict) -> None:
    """The per-participant ORIENT->PERCEIVE->...->CHECK TASK loop itself isn't
    built (planning/07). What IS real here is the bookkeeping contract every
    future implementation of this handler must honour: mark the participant_run
    terminal, finalize the run once every participant_run is terminal
    (planning/06), and NOTIFY run_progress_{run_id} (planning/03 "Realtime") so
    the SSE stream reflects it. That contract is exercised end-to-end below
    around a placeholder failure, then this always raises so the job row itself
    is marked FAILED like any other unimplemented handler."""
    runs = SimulationRunService(session)
    run_id = uuid.UUID(payload["simulation_run_id"])
    participant_run_id = uuid.UUID(payload["participant_run_id"])

    participant_run = await runs.get_participant_run(participant_run_id)
    participant_run.status = "FAILED"
    participant_run.final_outcome = {"error": "not_implemented"}
    participant_run.completed_at = datetime.now(UTC)
    await session.flush()

    if await runs.is_run_complete(run_id):
        await runs.finalize_run(run_id)

    run = await runs.get_by_id(run_id)
    snapshot = {
        "status": run.status,
        "completed": await runs.count_terminal(run_id),
        "total": await runs.count_total(run_id),
    }
    await session.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": f"run_progress_{run_id}", "payload": json.dumps(snapshot)},
    )

    raise NotImplementedError(_NOT_IMPLEMENTED_MESSAGE)
