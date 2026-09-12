import uuid
from unittest.mock import AsyncMock, Mock

from app.workers.jobs import aggregate_run as job_module


class _FakeSession:
    """Only `.execute()` (the idempotency deletes) and `.add_all()` (the new
    metric/segment rows) are exercised — every Service is monkeypatched out."""

    def __init__(self) -> None:
        self.executed: list = []
        self.added: list = []

    async def execute(self, stmt) -> None:
        self.executed.append(stmt)

    def add_all(self, rows) -> None:
        self.added.extend(rows)


def _participant_run(status: str, participant_id: uuid.UUID | None) -> Mock:
    return Mock(
        id=uuid.uuid4(),
        status=status,
        participant_id=participant_id,
        started_at=None,
        completed_at=None,
    )


def _observation(participant_run_id, type_, element_id=None, duration_ms=None, sequence_no=0):
    return Mock(
        participant_run_id=participant_run_id,
        type=type_,
        screen_id=None,
        element_id=element_id,
        duration_ms=duration_ms,
        sequence_no=sequence_no,
    )


def _patch_services(monkeypatch, *, run, participant_runs, observations, participants_by_id, task):
    fake_runs = AsyncMock()
    fake_runs.get_by_id.return_value = run
    fake_results = AsyncMock()
    fake_results.list_participant_runs.return_value = participant_runs
    fake_results.list_all_observations.return_value = observations
    fake_tasks = AsyncMock()
    fake_tasks.get_by_id.return_value = task
    fake_stimuli = AsyncMock()
    fake_audiences = AsyncMock()
    fake_audiences.list_by_ids.return_value = participants_by_id
    fake_jobs = AsyncMock()

    monkeypatch.setattr(job_module, "SimulationRunService", lambda session: fake_runs)
    monkeypatch.setattr(job_module, "ResultsService", lambda session: fake_results)
    monkeypatch.setattr(job_module, "TaskService", lambda session: fake_tasks)
    monkeypatch.setattr(job_module, "StimulusService", lambda session: fake_stimuli)
    monkeypatch.setattr(job_module, "AudienceService", lambda session: fake_audiences)
    monkeypatch.setattr(job_module, "JobService", lambda session: fake_jobs)
    return fake_jobs, fake_stimuli


async def test_aggregate_run_computes_and_persists_metrics_without_a_task(monkeypatch):
    """A run whose `task_id` wasn't resolvable (e.g. an older row from before
    that column existed) must still get every metric that doesn't depend on the
    task's `expected_critical_actions` — only `excess_actions`/`excess_screens`
    are skipped."""
    run_id = uuid.uuid4()
    run = Mock(id=run_id, task_id=None, study_id=uuid.uuid4())
    pr1 = _participant_run("COMPLETED", uuid.uuid4())
    pr2 = _participant_run("FAILED", uuid.uuid4())
    observations = [
        _observation(pr1.id, "SCREEN_ENTER", sequence_no=0),
        _observation(pr1.id, "CLICK", element_id=uuid.uuid4(), sequence_no=1),
    ]
    participants_by_id = {
        pr1.participant_id: Mock(traits={"digital_confidence": 0.9}),
        pr2.participant_id: Mock(traits={"digital_confidence": 0.1}),
    }

    fake_jobs, fake_stimuli = _patch_services(
        monkeypatch,
        run=run,
        participant_runs=[pr1, pr2],
        observations=observations,
        participants_by_id=participants_by_id,
        task=None,
    )
    session = _FakeSession()

    await job_module.handle_aggregate_run(session, {"simulation_run_id": str(run_id)})

    fake_stimuli.get_screen_graph.assert_not_awaited()
    assert len(session.executed) == 2  # delete metrics, delete segment_results
    metric_rows = [r for r in session.added if isinstance(r, job_module.MetricModel)]
    assert any(r.metric == "completion_rate" and r.value == 0.5 for r in metric_rows)
    assert not any(r.metric in ("excess_actions", "excess_screens") for r in metric_rows)
    segment_rows = [r for r in session.added if isinstance(r, job_module.SegmentResultModel)]
    assert {r.segment for r in segment_rows} == {
        "digital_confidence_low",
        "digital_confidence_high",
    }
    fake_jobs.enqueue.assert_awaited_once_with("validate_run", {"simulation_run_id": str(run_id)})


async def test_aggregate_run_computes_baseline_metrics_when_task_is_resolvable(monkeypatch):
    from app.agents.types import ElementView, ScreenGraph, ScreenView

    run_id = uuid.uuid4()
    study_id = uuid.uuid4()
    home_id = uuid.uuid4()
    cta_id = uuid.uuid4()
    run = Mock(id=run_id, task_id=uuid.uuid4(), study_id=study_id)
    task = Mock(starting_point=None, expected_critical_actions=["cta"])
    screen_graph = ScreenGraph(
        screens={
            home_id: ScreenView(
                id=home_id,
                screen_key="home",
                width=None,
                height=None,
                elements=[
                    ElementView(
                        id=cta_id,
                        element_key="cta",
                        type="button",
                        text=None,
                        bbox=(0, 0, 10, 10),
                        semantic_role="primary_action",
                        interactable=True,
                    )
                ],
            )
        },
        transitions=[],
    )
    pr1 = _participant_run("COMPLETED", uuid.uuid4())
    observations = [
        _observation(pr1.id, "SCREEN_ENTER", sequence_no=0),
        _observation(pr1.id, "CLICK", element_id=cta_id, sequence_no=1),
    ]

    fake_jobs, fake_stimuli = _patch_services(
        monkeypatch,
        run=run,
        participant_runs=[pr1],
        observations=observations,
        participants_by_id={},
        task=task,
    )
    fake_stimuli.get_screen_graph.return_value = screen_graph
    session = _FakeSession()

    await job_module.handle_aggregate_run(session, {"simulation_run_id": str(run_id)})

    fake_stimuli.get_screen_graph.assert_awaited_once_with(study_id)
    metric_rows = [r for r in session.added if isinstance(r, job_module.MetricModel)]
    # baseline is (1, 0): the critical element is already on the starting screen.
    assert any(r.metric == "excess_actions" and r.value == 0.0 for r in metric_rows)
    assert any(r.metric == "excess_screens" and r.value == 1.0 for r in metric_rows)
