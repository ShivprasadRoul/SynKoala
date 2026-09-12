import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graphs.simulation_graph import run_simulation
from app.agents.providers.participant_model import get_participant_model
from app.agents.types import ParticipantDraft, TaskContext
from app.core.errors import LifecycleError
from app.db.models import ObservationModel, TaskModel
from app.services.audience_service import AudienceService
from app.services.job_service import JobService
from app.services.simulation_run_service import SimulationRunService
from app.services.stimulus_service import StimulusService
from app.services.task_service import TaskService

_TERMINAL_STATUS = {"COMPLETED": "COMPLETED", "FAILED": "FAILED", "ABANDONED": "ABANDONED"}


def _task_context_from_orm(task: TaskModel) -> TaskContext:
    return TaskContext(
        id=task.id,
        instruction=task.instruction,
        starting_point=task.starting_point,
        success_conditions=task.success_conditions,
        constraints=task.constraints,
        expected_critical_actions=task.expected_critical_actions,
    )


async def _finalize_run_and_notify(
    session: AsyncSession, runs: SimulationRunService, jobs: JobService, run_id: uuid.UUID
) -> None:
    """Shared by the normal completion path and the permanent-job-failure
    fallback below — both need the exact same "am I the last participant?"
    bookkeeping (planning/06-study-orchestrator.md item 4)."""
    if await runs.is_run_complete(run_id):
        run = await runs.finalize_run(run_id)
        if run.status in ("COMPLETED", "FAILED"):
            # First link of the aggregate_run -> validate_run -> generate_insights
            # chain (planning/06's "Job chain"). Triggered for FAILED too, not
            # just COMPLETED: `finalize_run` marks a run FAILED whenever *zero*
            # participants completed, but that's precisely the population-level
            # result — task success is the headline metric, and 0% completion
            # is a headline result, not a reason to skip analysis. Skipping it
            # here used to mean a 100%-drop-off run got no metrics/friction/
            # discoverability analysis at all, exactly when that analysis
            # matters most (PRD §7's own "friction explains why success isn't
            # higher" framing). Only CANCELLING->CANCELLED (a researcher-
            # interrupted run, not one that reached its own terminal state)
            # still skips this.
            await jobs.enqueue("aggregate_run", {"simulation_run_id": str(run_id)})

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


def _derive_participant_seed(run_seed: int | None, participant_id: uuid.UUID) -> str:
    """Every participant must get its own reproducible-but-distinct RNG stream
    (PRD §7) — the run-level `seed` alone can't be reused verbatim for every
    participant or population diversity would collapse whenever two
    participants share trait values. `random.Random` seeds strings via a
    stable hash (unlike the built-in `hash()`, which is process-randomized),
    so this stays reproducible across processes/runs."""
    return f"{run_seed if run_seed is not None else 'unseeded'}:{participant_id}"


async def handle_simulate_participant(session: AsyncSession, payload: dict) -> None:
    """The Simulation Engine loop itself (planning/07-simulation-engine.md,
    LLD §8-§13) — runs `app.agents.graphs.simulation_graph` for one participant,
    persists the resulting `observations`, and marks the `participant_runs`/
    `simulation_runs` bookkeeping terminal, NOTIFYing `run_progress_{run_id}`
    (planning/03 "Realtime") so the SSE stream reflects it either way."""
    runs = SimulationRunService(session)
    audiences = AudienceService(session)
    tasks = TaskService(session)
    stimuli = StimulusService(session)
    jobs = JobService(session)

    run_id = uuid.UUID(payload["simulation_run_id"])
    participant_run_id = uuid.UUID(payload["participant_run_id"])
    participant_id = uuid.UUID(payload["participant_id"])
    study_id = uuid.UUID(payload["study_id"])
    task_id = uuid.UUID(payload["task_id"])

    run = await runs.get_by_id(run_id)
    participant_run = await runs.get_participant_run(participant_run_id)
    participant_record = await audiences.get_participant(participant_id)
    task = await tasks.get_by_id(task_id)
    screen_graph = await stimuli.get_screen_graph(study_id)

    if not any(screen.elements for screen in screen_graph.screens.values()):
        raise LifecycleError(
            f"Study {study_id} has no analyzed screens yet "
            "(planning/05-stimulus-engine.md's VisionProvider hasn't run for its stimuli)"
        )

    task_context = _task_context_from_orm(task)
    participant = ParticipantDraft(
        id=participant_record.id,
        traits=participant_record.traits,
        persona=participant_record.persona,
    )
    participant_model = get_participant_model(
        (run.config or {}).get("participant_model") if run.config else None
    )
    seed = _derive_participant_seed(run.seed, participant_record.id)

    final_state = await run_simulation(
        participant=participant,
        task=task_context,
        screen_graph=screen_graph,
        starting_screen_id=screen_graph.resolve_starting_screen(task_context.starting_point),
        seed=seed,
        participant_model=participant_model,
    )

    observations = [
        ObservationModel(
            participant_run_id=participant_run_id,
            sequence_no=event["sequence_no"],
            type=event["type"],
            screen_id=event["screen_id"],
            element_id=event["element_id"],
            x=event["x"],
            y=event["y"],
            duration_ms=event["duration_ms"],
            payload=event["payload"],
        )
        for event in final_state["events"]
    ]
    session.add_all(observations)

    outcome = final_state["outcome"]
    await runs.complete_participant_run(
        participant_run,
        status=_TERMINAL_STATUS.get(outcome, "FAILED"),
        final_outcome={
            "task_progress": final_state["task_progress"],
            "failure_reason": final_state["failure_reason"],
            "steps": final_state["step"],
            "events_written": len(observations),
        },
        current_screen_id=final_state["current_screen_id"],
    )
    await _finalize_run_and_notify(session, runs, jobs, run_id)


async def handle_simulate_participant_permanent_failure(
    session: AsyncSession, payload: dict
) -> None:
    """Runs once `app/workers/runner.py` gives up retrying a `simulate_participant`
    job (after `MAX_ATTEMPTS`). Without this, a participant whose job fails
    before `handle_simulate_participant` ever reaches `complete_participant_run`
    (e.g. the "no analyzed screens yet" `LifecycleError` above) leaves its
    `participant_runs` row PENDING forever — `is_run_complete` then never sees
    every participant as terminal, so the run itself could never finalize. The
    PRD §7 reliability requirement is explicit that a job-level failure must be
    "recorded as a failed participant, never failing the whole run"
    (planning/06-study-orchestrator.md item 4) — this is what makes that hold
    even when the failure happens before any bookkeeping write."""
    runs = SimulationRunService(session)
    jobs = JobService(session)
    run_id = uuid.UUID(payload["simulation_run_id"])
    participant_run_id = uuid.UUID(payload["participant_run_id"])

    participant_run = await runs.get_participant_run(participant_run_id)
    if participant_run.status not in ("COMPLETED", "FAILED", "ABANDONED"):
        await runs.complete_participant_run(
            participant_run, status="FAILED", final_outcome={"error": "job_permanently_failed"}
        )

    await _finalize_run_and_notify(session, runs, jobs, run_id)
