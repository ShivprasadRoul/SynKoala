from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.workers.jobs.analyze_stimulus import handle_analyze_stimulus
from app.workers.jobs.simulate_participant import handle_simulate_participant

JobHandler = Callable[[AsyncSession, dict], Awaitable[None]]

HANDLERS: dict[str, JobHandler] = {
    "analyze_stimulus": handle_analyze_stimulus,
    "simulate_participant": handle_simulate_participant,
}
