import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.types import ScreenGraph
from app.db.models import MetricModel, ObservationModel, SegmentResultModel
from app.services.analytics_engine import AnalyticsEngine, ObservationRow, ParticipantRunData
from app.services.audience_service import AudienceService
from app.services.job_service import JobService
from app.services.results_service import ResultsService
from app.services.simulation_run_service import SimulationRunService
from app.services.stimulus_service import StimulusService
from app.services.task_service import TaskService


def _task_time_ms(participant_run) -> float | None:
    if participant_run.started_at is None or participant_run.completed_at is None:
        return None
    return (participant_run.completed_at - participant_run.started_at).total_seconds() * 1000


def _observation_row(observation: ObservationModel) -> ObservationRow:
    return ObservationRow(
        type=observation.type,
        screen_id=observation.screen_id,
        element_id=observation.element_id,
        duration_ms=observation.duration_ms,
        sequence_no=observation.sequence_no,
    )


def _critical_element_ids(screen_graph: ScreenGraph, critical_actions: list[str] | None) -> set:
    critical = set(critical_actions or [])
    if not critical:
        return set()
    return {
        element.id
        for screen in screen_graph.screens.values()
        for element in screen.elements
        if {element.element_key, element.semantic_role or ""} & critical
    }


async def handle_aggregate_run(session: AsyncSession, payload: dict) -> None:
    """The Analytics Engine's job (planning/09-analytics-engine.md): runs once
    every `simulate_participant` job for the run is terminal
    (`app/workers/jobs/simulate_participant.py:_finalize_run_and_notify`).
    Computes task-success/friction/discoverability metrics and per-segment
    results directly from persisted `observations` (never a screenshot, HLD
    §1's key rule — see `AnalyticsEngine`'s own docstring), replaces any
    previously-computed rows for this run (idempotent under the worker's own
    retry-on-failure policy), and enqueues `validate_run` (planning/10, also
    real now)."""
    run_id = uuid.UUID(payload["simulation_run_id"])

    runs = SimulationRunService(session)
    results = ResultsService(session)
    tasks = TaskService(session)
    stimuli = StimulusService(session)
    audiences = AudienceService(session)
    jobs = JobService(session)
    engine = AnalyticsEngine()

    run = await runs.get_by_id(run_id)
    participant_runs = await results.list_participant_runs(run_id)
    observations = await results.list_all_observations(run_id)

    observations_by_run: dict[uuid.UUID, list[ObservationRow]] = {}
    for observation in observations:
        observations_by_run.setdefault(observation.participant_run_id, []).append(
            _observation_row(observation)
        )

    participant_ids = [pr.participant_id for pr in participant_runs if pr.participant_id]
    participants_by_id = await audiences.list_by_ids(participant_ids)

    participant_data = [
        ParticipantRunData(
            id=pr.id,
            status=pr.status,
            task_time_ms=_task_time_ms(pr),
            traits=(
                participants_by_id[pr.participant_id].traits
                if pr.participant_id in participants_by_id
                else None
            ),
            observations=observations_by_run.get(pr.id, []),
        )
        for pr in participant_runs
    ]

    task = await tasks.get_by_id(run.task_id) if run.task_id is not None else None
    baseline = None
    critical_element_ids: set = set()
    if task is not None:
        screen_graph = await stimuli.get_screen_graph(run.study_id)
        critical_element_ids = _critical_element_ids(screen_graph, task.expected_critical_actions)
        try:
            start_screen_id = screen_graph.resolve_starting_screen(task.starting_point)
        except ValueError:
            start_screen_id = None
        if start_screen_id is not None:
            baseline = engine.shortest_path_baseline(
                screen_graph, start_screen_id, task.expected_critical_actions
            )

    metric_rows = engine.compute_metrics(participant_data, baseline)
    segment_rows = engine.compute_segments(participant_data, critical_element_ids)

    # Idempotent under retry: a prior attempt that computed rows but failed
    # before `validate_run` was enqueued (or before the job's own commit) must
    # not leave duplicates behind on the next attempt.
    await session.execute(delete(MetricModel).where(MetricModel.simulation_run_id == run_id))
    await session.execute(
        delete(SegmentResultModel).where(SegmentResultModel.simulation_run_id == run_id)
    )
    session.add_all(
        MetricModel(
            simulation_run_id=run_id,
            level=row.level,
            metric=row.metric,
            element_id=row.element_id,
            screen_id=row.screen_id,
            value=row.value,
            sample_size=row.sample_size,
        )
        for row in metric_rows
    )
    session.add_all(
        SegmentResultModel(
            simulation_run_id=run_id,
            segment=row.segment,
            metric=row.metric,
            value=row.value,
            sample_size=row.sample_size,
        )
        for row in segment_rows
    )

    await jobs.enqueue("validate_run", {"simulation_run_id": str(run_id)})
