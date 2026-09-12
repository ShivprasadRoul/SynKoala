import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graphs.simulation_graph import run_simulation
from app.agents.providers.participant_model import get_participant_model
from app.agents.types import (
    ElementView,
    ParticipantDraft,
    ScreenGraph,
    ScreenView,
    TaskContext,
    TransitionView,
)
from app.core.errors import LifecycleError
from app.db.models import ObservationModel, ScreenModel, ScreenTransitionModel, TaskModel
from app.services.audience_service import AudienceService
from app.services.simulation_run_service import SimulationRunService
from app.services.stimulus_service import StimulusService
from app.services.task_service import TaskService

_TERMINAL_STATUS = {"COMPLETED": "COMPLETED", "FAILED": "FAILED", "ABANDONED": "ABANDONED"}


def _infer_interactable(element_type: str, properties: dict) -> bool:
    if "interactable" in properties:
        return bool(properties["interactable"])
    return element_type in ("button", "input", "link", "select", "checkbox", "radio")


def _element_view_from_orm(element) -> ElementView:
    properties = element.properties or {}
    return ElementView(
        id=element.id,
        element_key=element.element_key,
        type=element.type,
        text=element.text,
        bbox=tuple(element.bbox),
        semantic_role=properties.get("semantic_role"),
        interactable=_infer_interactable(element.type, properties),
    )


def _screen_graph_from_orm(
    screens: list[ScreenModel], transitions: list[ScreenTransitionModel]
) -> ScreenGraph:
    """Converts the Stimulus Engine's persisted rows (planning/05) into the
    Simulation Engine's own types (planning/07). `properties` is where the
    VisionProvider's `semantic_role`/`interactable` fields live — `ui_elements`
    has no dedicated columns for them (LLD §3)."""
    screen_views = {
        screen.id: ScreenView(
            id=screen.id,
            screen_key=screen.screen_key,
            width=screen.width,
            height=screen.height,
            elements=[_element_view_from_orm(element) for element in screen.elements],
        )
        for screen in screens
    }
    transition_views = [
        TransitionView(
            from_screen_id=t.from_screen_id,
            trigger_element_id=t.trigger_element_id,
            action=t.action,
            to_screen_id=t.to_screen_id,
        )
        for t in transitions
    ]
    return ScreenGraph(screens=screen_views, transitions=transition_views)


def _task_context_from_orm(task: TaskModel) -> TaskContext:
    return TaskContext(
        id=task.id,
        instruction=task.instruction,
        starting_point=task.starting_point,
        success_conditions=task.success_conditions,
        constraints=task.constraints,
        expected_critical_actions=task.expected_critical_actions,
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

    run_id = uuid.UUID(payload["simulation_run_id"])
    participant_run_id = uuid.UUID(payload["participant_run_id"])
    participant_id = uuid.UUID(payload["participant_id"])
    study_id = uuid.UUID(payload["study_id"])
    task_id = uuid.UUID(payload["task_id"])

    run = await runs.get_by_id(run_id)
    participant_run = await runs.get_participant_run(participant_run_id)
    participant_record = await audiences.get_participant(participant_id)
    task = await tasks.get_by_id(task_id)
    screens = await stimuli.list_screens_for_study(study_id)
    transitions = await stimuli.list_transitions_for_study(study_id)

    if not any(screen.elements for screen in screens):
        raise LifecycleError(
            f"Study {study_id} has no analyzed screens yet "
            "(planning/05-stimulus-engine.md's VisionProvider hasn't run for its stimuli)"
        )

    screen_graph = _screen_graph_from_orm(screens, transitions)
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
    if await runs.is_run_complete(run_id):
        await runs.finalize_run(run_id)

    snapshot = {
        "status": run.status,
        "completed": await runs.count_terminal(run_id),
        "total": await runs.count_total(run_id),
    }
    await session.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": f"run_progress_{run_id}", "payload": json.dumps(snapshot)},
    )
