import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.routes import SimulationsRoutes
from app.core.auth import get_current_user
from app.db.listen import get_listen_connection
from app.db.models import UserModel
from app.db.session import get_session
from app.domain.schemas.simulation import (
    SimulationRunCreate,
    SimulationRunRead,
    SimulationRunSummary,
)
from app.usecases.simulations import SimulationUseCase

simulations_router_v1 = APIRouter(tags=SimulationsRoutes.TAGS)

_TERMINAL_STATUSES = ("COMPLETED", "FAILED", "CANCELLED")
_NOTIFY_WAIT_SECONDS = 1
_PROGRESS_MAX_TICKS = 300  # 5 minutes safety cap — see planning/02-api.md "SSE endpoint"


@simulations_router_v1.post(
    SimulationsRoutes.CREATE, response_model=SimulationRunRead, status_code=status.HTTP_201_CREATED
)
async def create_simulation_run(
    study_id: uuid.UUID,
    body: SimulationRunCreate,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SimulationRunRead:
    use_case = SimulationUseCase(session)
    run = await use_case.create_run(
        current_user, study_id, body.population_size, body.task_id, body.config, body.seed
    )
    return SimulationRunRead.model_validate(run)


@simulations_router_v1.get(SimulationsRoutes.LIST, response_model=list[SimulationRunSummary])
async def list_simulation_runs(
    study_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[SimulationRunSummary]:
    use_case = SimulationUseCase(session)
    rows = await use_case.list_runs(current_user, study_id)
    return [
        SimulationRunSummary(
            id=row["run"].id,
            status=row["run"].status,
            population_size=row["run"].population_size,
            source=row["run"].source,
            seed=row["run"].seed,
            created_at=row["run"].created_at,
            started_at=row["run"].started_at,
            completed_at=row["run"].completed_at,
            completion_rate=row["completion_rate"],
        )
        for row in rows
    ]


@simulations_router_v1.post(
    SimulationsRoutes.PUBLISH, response_model=SimulationRunRead, status_code=status.HTTP_201_CREATED
)
async def publish_study(
    study_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SimulationRunRead:
    """Publishes a DRAFT study and starts its first simulation run in one
    request — see `SimulationUseCase.publish` for the atomicity this relies
    on. Returns the created run so the caller can navigate straight to its
    results page."""
    use_case = SimulationUseCase(session)
    run = await use_case.publish(current_user, study_id)
    return SimulationRunRead.model_validate(run)


@simulations_router_v1.get(SimulationsRoutes.DETAIL, response_model=SimulationRunRead)
async def get_simulation_run(
    run_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SimulationRunRead:
    use_case = SimulationUseCase(session)
    run = await use_case.get_run(current_user, run_id)
    return SimulationRunRead.model_validate(run)


@simulations_router_v1.post(
    SimulationsRoutes.CANCEL, response_model=SimulationRunRead, status_code=status.HTTP_202_ACCEPTED
)
async def cancel_simulation_run(
    run_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SimulationRunRead:
    use_case = SimulationUseCase(session)
    run = await use_case.cancel_run(current_user, run_id)
    return SimulationRunRead.model_validate(run)


@simulations_router_v1.get(SimulationsRoutes.PROGRESS)
async def simulation_progress(
    run_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """planning/02-api.md "SSE endpoint": real Postgres LISTEN/NOTIFY. The worker
    (app/workers/jobs/simulate_participant.py) issues `NOTIFY run_progress_{run_id}`
    after each participant job's terminal outcome; this listens on that channel
    instead of polling the DB. Still capped at 5 minutes — if no worker is running,
    or a run's jobs never get claimed, or a NOTIFY is dropped, the stream ends
    rather than hanging forever."""
    use_case = SimulationUseCase(session)

    async def event_stream():
        snapshot = await use_case.get_progress(current_user, run_id)
        if snapshot["status"] in _TERMINAL_STATUSES:
            yield f"event: simulation.completed\ndata: {json.dumps(snapshot)}\n\n"
            return
        yield f"event: simulation.progress\ndata: {json.dumps(snapshot)}\n\n"

        channel = f"run_progress_{run_id}"
        queue: asyncio.Queue[str] = asyncio.Queue()

        def _on_notify(_conn: object, _pid: int, _channel: str, payload: str) -> None:
            queue.put_nowait(payload)

        conn = await get_listen_connection()
        await conn.add_listener(channel, _on_notify)
        try:
            for _ in range(_PROGRESS_MAX_TICKS):
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=_NOTIFY_WAIT_SECONDS)
                except TimeoutError:
                    continue
                data = json.loads(payload)
                terminal = data["status"] in _TERMINAL_STATUSES
                event = "simulation.completed" if terminal else "simulation.progress"
                yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
                if terminal:
                    return
        finally:
            await conn.remove_listener(channel, _on_notify)
            await conn.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
