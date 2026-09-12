from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.workers.jobs.aggregate_run import handle_aggregate_run
from app.workers.jobs.analyze_stimulus import handle_analyze_stimulus
from app.workers.jobs.import_figma_prototype import handle_import_figma_prototype
from app.workers.jobs.simulate_participant import (
    handle_simulate_participant,
    handle_simulate_participant_permanent_failure,
)

JobHandler = Callable[[AsyncSession, dict], Awaitable[None]]

HANDLERS: dict[str, JobHandler] = {
    "analyze_stimulus": handle_analyze_stimulus,
    "simulate_participant": handle_simulate_participant,
    "aggregate_run": handle_aggregate_run,
    "import_figma_prototype": handle_import_figma_prototype,
}

# Run once a job exhausts its retries (app/workers/runner.py's MAX_ATTEMPTS) — lets a
# job type record its own "permanently failed" bookkeeping (planning/06-study-
# orchestrator.md item 4's reliability requirement) instead of leaving a related row
# (e.g. participant_runs) dangling PENDING forever. Optional: most job types don't need
# one.
ON_PERMANENT_FAILURE: dict[str, JobHandler] = {
    "simulate_participant": handle_simulate_participant_permanent_failure,
}
