import uuid
from unittest.mock import ANY, AsyncMock, Mock

import pytest

from app.agents.types import ScreenGraph, ScreenView
from app.core.errors import LifecycleError
from app.db.models import ParticipantRecordModel, StudyModel, TaskModel
from app.usecases.simulations import SimulationUseCase


class _NoOpSession:
    async def commit(self) -> None:
        pass


def _ready_study(status: str = "READY") -> StudyModel:
    return StudyModel(id=uuid.uuid4(), project_id=uuid.uuid4(), name="Study", status=status)


def _screen_graph_with(*screen_keys: str) -> ScreenGraph:
    screens = {}
    for key in screen_keys:
        screen_id = uuid.uuid4()
        screens[screen_id] = ScreenView(
            id=screen_id, screen_key=key, width=None, height=None, elements=[]
        )
    return ScreenGraph(screens=screens, transitions=[])


def _use_case_with_ready_study(study: StudyModel) -> SimulationUseCase:
    use_case = SimulationUseCase(_NoOpSession())
    use_case._studies = AsyncMock()
    use_case._studies.get_owned.return_value = study
    use_case._stimuli = AsyncMock()
    # Empty by default — fine for tests whose task sets neither starting_point
    # nor success_conditions.screen_key, so _verify_screen_keys_exist has
    # nothing to check against real screens.
    use_case._stimuli.get_screen_graph.return_value = _screen_graph_with()
    use_case._tasks = AsyncMock()
    use_case._audiences = AsyncMock()
    use_case._runs = AsyncMock()
    # No prior runs by default — most tests aren't exercising the
    # one-active-run-at-a-time guard, which needs a real list to iterate.
    use_case._runs.list_by_study.return_value = []
    use_case._results = AsyncMock()
    use_case._jobs = AsyncMock()
    return use_case


def _completable_task(study_id: uuid.UUID) -> TaskModel:
    return TaskModel(
        id=uuid.uuid4(),
        study_id=study_id,
        instruction="Do the thing",
        success_conditions={"screen_key": "done_screen"},
    )


def _wire_for_a_runnable_study(use_case: SimulationUseCase, study: StudyModel) -> TaskModel:
    """Arranges every dependency create_run/publish needs to succeed, for
    tests that care about population_size defaulting or publish's own
    orchestration rather than re-testing create_run's individual guards."""
    task = _completable_task(study.id)
    participant = ParticipantRecordModel(id=uuid.uuid4(), audience_id=uuid.uuid4(), traits={})
    use_case._stimuli.has_analyzed_screens.return_value = True
    use_case._stimuli.get_screen_graph.return_value = _screen_graph_with("done_screen")
    use_case._tasks.list_for_study.return_value = [task]
    use_case._audiences.get_latest_for_study.return_value = Mock(id=uuid.uuid4())
    use_case._audiences.list_participants.return_value = [participant] * 100
    use_case._runs.create_run.return_value = Mock(id=uuid.uuid4())
    use_case._runs.create_participant_run.return_value = Mock(id=uuid.uuid4())
    return task


async def test_create_run_rejects_study_with_no_analyzed_stimulus():
    study = _ready_study()
    use_case = _use_case_with_ready_study(study)
    use_case._stimuli.has_analyzed_screens.return_value = False

    with pytest.raises(LifecycleError, match="no analyzed stimulus"):
        await use_case.create_run(
            user=Mock(), study_id=study.id, population_size=1, task_id=None, config=None, seed=None
        )

    use_case._tasks.list_for_study.assert_not_awaited()
    use_case._runs.create_run.assert_not_awaited()


async def test_create_run_proceeds_once_stimulus_is_analyzed():
    study = _ready_study()
    task = TaskModel(
        id=uuid.uuid4(),
        study_id=study.id,
        instruction="Do the thing",
        success_conditions={"screen_key": "done_screen"},
    )
    participant = ParticipantRecordModel(id=uuid.uuid4(), audience_id=uuid.uuid4(), traits={})

    use_case = _use_case_with_ready_study(study)
    use_case._stimuli.has_analyzed_screens.return_value = True
    use_case._stimuli.get_screen_graph.return_value = _screen_graph_with("done_screen")
    use_case._tasks.list_for_study.return_value = [task]
    use_case._audiences.get_latest_for_study.return_value = Mock(id=uuid.uuid4())
    use_case._audiences.list_participants.return_value = [participant]
    fake_run = Mock(id=uuid.uuid4())
    use_case._runs.create_run.return_value = fake_run
    use_case._runs.create_participant_run.return_value = Mock(id=uuid.uuid4())

    result = await use_case.create_run(
        user=Mock(), study_id=study.id, population_size=1, task_id=None, config=None, seed=42
    )

    assert result is fake_run
    use_case._jobs.enqueue.assert_awaited_once()
    job_type, job_payload = use_case._jobs.enqueue.await_args.args
    assert job_type == "simulate_participant"
    assert job_payload["seed"] == 42


@pytest.mark.parametrize("status", ["RUNNING", "COMPLETED"])
async def test_create_run_allows_a_second_run_once_the_study_has_already_run_one(status):
    """The bug this closes: create_run itself moves a study to RUNNING, and
    STUDY_STATUS_TRANSITIONS has no path back from RUNNING/COMPLETED to
    READY — gating a second run on `status == "READY"` made any study
    permanently one-run-only, which breaks run_stability_cv (planning/10,
    needs >= 5 repeated runs of the same study) and baseline-comparison runs
    outright."""
    study = _ready_study(status=status)
    task = TaskModel(
        id=uuid.uuid4(),
        study_id=study.id,
        instruction="Do the thing",
        success_conditions={"screen_key": "done_screen"},
    )
    participant = ParticipantRecordModel(id=uuid.uuid4(), audience_id=uuid.uuid4(), traits={})

    use_case = _use_case_with_ready_study(study)
    use_case._stimuli.has_analyzed_screens.return_value = True
    use_case._stimuli.get_screen_graph.return_value = _screen_graph_with("done_screen")
    use_case._tasks.list_for_study.return_value = [task]
    use_case._audiences.get_latest_for_study.return_value = Mock(id=uuid.uuid4())
    use_case._audiences.list_participants.return_value = [participant]
    use_case._runs.create_run.return_value = Mock(id=uuid.uuid4())
    use_case._runs.create_participant_run.return_value = Mock(id=uuid.uuid4())

    await use_case.create_run(
        user=Mock(), study_id=study.id, population_size=1, task_id=None, config=None, seed=None
    )

    use_case._runs.create_run.assert_awaited_once()


@pytest.mark.parametrize(
    "task_kwargs",
    [
        {},
        # A dict using none of screen_key/element_key/semantic_role has no
        # evaluation semantics anywhere, so it's no more a finish line than None.
        {"success_conditions": {"beneficiary_credited": True}},
    ],
)
async def test_create_run_rejects_a_task_with_no_finish_line(task_kwargs):
    """Without a recognized success condition or critical actions, update_state
    caps task_progress at 0.9 by exploration alone — every participant is
    guaranteed to abandon at max_steps. Refuse the run rather than emit a 100%
    drop-off that reads like a real finding about the interface."""
    study = _ready_study()
    task = TaskModel(id=uuid.uuid4(), study_id=study.id, instruction="Do the thing", **task_kwargs)

    use_case = _use_case_with_ready_study(study)
    use_case._stimuli.has_analyzed_screens.return_value = True
    use_case._tasks.list_for_study.return_value = [task]

    with pytest.raises(LifecycleError, match="no finish line"):
        await use_case.create_run(
            user=Mock(), study_id=study.id, population_size=1, task_id=None, config=None, seed=None
        )

    use_case._runs.create_run.assert_not_awaited()


async def test_create_run_accepts_critical_actions_as_the_finish_line():
    """expected_critical_actions alone can still complete a task (the
    pre-existing contract) — the guard only rejects a task with neither."""
    study = _ready_study()
    task = TaskModel(
        id=uuid.uuid4(),
        study_id=study.id,
        instruction="Do the thing",
        expected_critical_actions=["add_to_cart"],
    )
    participant = ParticipantRecordModel(id=uuid.uuid4(), audience_id=uuid.uuid4(), traits={})

    use_case = _use_case_with_ready_study(study)
    use_case._stimuli.has_analyzed_screens.return_value = True
    use_case._tasks.list_for_study.return_value = [task]
    use_case._audiences.get_latest_for_study.return_value = Mock(id=uuid.uuid4())
    use_case._audiences.list_participants.return_value = [participant]
    use_case._runs.create_run.return_value = Mock(id=uuid.uuid4())
    use_case._runs.create_participant_run.return_value = Mock(id=uuid.uuid4())

    await use_case.create_run(
        user=Mock(), study_id=study.id, population_size=1, task_id=None, config=None, seed=None
    )

    use_case._runs.create_run.assert_awaited_once()


@pytest.mark.parametrize("status", ["DRAFT", "FAILED"])
async def test_create_run_still_rejects_a_study_that_was_never_readied(status):
    study = _ready_study(status=status)
    use_case = _use_case_with_ready_study(study)

    with pytest.raises(LifecycleError, match="must be READY"):
        await use_case.create_run(
            user=Mock(), study_id=study.id, population_size=1, task_id=None, config=None, seed=None
        )

    use_case._runs.create_run.assert_not_awaited()


async def test_cancel_run_finalizes_immediately_once_no_participants_are_left_in_progress():
    """The bug this closes: a cancelled job never reaches
    complete_participant_run, so its participant_runs row would stay PENDING
    forever unless cancel_run abandons it itself — and once that was every
    remaining participant, nothing else is left running to trigger
    finalize_run later, so cancel_run must do it inline."""
    study = _ready_study()
    run = Mock(id=uuid.uuid4(), study_id=study.id, status="RUNNING")
    use_case = _use_case_with_ready_study(study)
    use_case._runs.get_by_id.return_value = run
    use_case._runs.mark_cancelling.return_value = run
    use_case._runs.is_run_complete.return_value = True
    finalized = Mock(status="CANCELLED")
    use_case._runs.finalize_run.return_value = finalized

    result = await use_case.cancel_run(user=Mock(), run_id=run.id)

    use_case._runs.mark_cancelling.assert_awaited_once_with(run)
    use_case._jobs.cancel_pending.assert_awaited_once_with(
        "simulate_participant", "simulation_run_id", str(run.id)
    )
    use_case._runs.abandon_pending_participant_runs.assert_awaited_once_with(run.id)
    use_case._runs.finalize_run.assert_awaited_once_with(run.id)
    assert result is finalized


async def test_cancel_run_leaves_finalizing_to_the_worker_when_participants_are_still_in_progress():
    study = _ready_study()
    run = Mock(id=uuid.uuid4(), study_id=study.id, status="RUNNING")
    use_case = _use_case_with_ready_study(study)
    use_case._runs.get_by_id.return_value = run
    use_case._runs.mark_cancelling.return_value = run
    use_case._runs.is_run_complete.return_value = False

    result = await use_case.cancel_run(user=Mock(), run_id=run.id)

    use_case._runs.finalize_run.assert_not_awaited()
    assert result is run


async def test_cancel_run_rejects_an_already_terminal_run():
    study = _ready_study()
    run = Mock(id=uuid.uuid4(), study_id=study.id, status="COMPLETED")
    use_case = _use_case_with_ready_study(study)
    use_case._runs.get_by_id.return_value = run

    with pytest.raises(LifecycleError, match="Cannot cancel"):
        await use_case.cancel_run(user=Mock(), run_id=run.id)

    use_case._runs.mark_cancelling.assert_not_awaited()
    use_case._runs.abandon_pending_participant_runs.assert_not_awaited()


# --- population_size defaulting from the study (item 1: no re-entering it) ---


async def test_create_run_defaults_population_size_from_the_study():
    study = _ready_study()
    study.population_size = 25
    use_case = _use_case_with_ready_study(study)
    _wire_for_a_runnable_study(use_case, study)

    await use_case.create_run(
        user=Mock(),
        study_id=study.id,
        population_size=None,
        task_id=None,
        config=None,
        seed=None,
    )

    use_case._runs.create_run.assert_awaited_once_with(study.id, 25, None, None, task_id=ANY)


async def test_create_run_rejects_when_neither_the_study_nor_the_caller_set_a_population_size():
    study = _ready_study()
    study.population_size = None
    use_case = _use_case_with_ready_study(study)

    with pytest.raises(LifecycleError, match="no configured sample size"):
        await use_case.create_run(
            user=Mock(),
            study_id=study.id,
            population_size=None,
            task_id=None,
            config=None,
            seed=None,
        )

    use_case._runs.create_run.assert_not_awaited()


async def test_create_run_prefers_an_explicit_population_size_over_the_studys_default():
    study = _ready_study()
    study.population_size = 25
    use_case = _use_case_with_ready_study(study)
    _wire_for_a_runnable_study(use_case, study)

    await use_case.create_run(
        user=Mock(), study_id=study.id, population_size=5, task_id=None, config=None, seed=None
    )

    use_case._runs.create_run.assert_awaited_once_with(study.id, 5, None, None, task_id=ANY)


# --- publish (item 3: publish creates + starts a run atomically) ---


def _mutate_study_status(study, **kwargs):
    if "status" in kwargs:
        study.status = kwargs["status"]
    return study


async def test_publish_transitions_the_study_to_ready_and_creates_a_run():
    study = _ready_study(status="DRAFT")
    study.population_size = 10
    use_case = _use_case_with_ready_study(study)
    _wire_for_a_runnable_study(use_case, study)
    # Mirrors StudyService.update's real contract: mutates the ORM object in
    # place (SQLAlchemy's identity map is what makes create_run's own
    # get_owned() see the transition in real code) rather than a mock that
    # returns a value with no effect on the object create_run re-fetches.
    use_case._studies.update.side_effect = _mutate_study_status

    run = await use_case.publish(user=Mock(), study_id=study.id)

    use_case._studies.update.assert_awaited_once_with(study, status="READY")
    use_case._runs.create_run.assert_awaited_once()
    assert run is use_case._runs.create_run.return_value


async def test_publish_rejects_a_study_that_is_already_published():
    """Publish is a one-time DRAFT -> READY action — a later simulation for an
    already-published study goes through create_run ("run again"), not a
    second publish."""
    study = _ready_study(status="READY")
    use_case = _use_case_with_ready_study(study)

    with pytest.raises(LifecycleError, match="already published"):
        await use_case.publish(user=Mock(), study_id=study.id)

    use_case._studies.update.assert_not_awaited()
    use_case._runs.create_run.assert_not_awaited()


async def test_publish_rejects_a_study_with_no_sample_size():
    study = _ready_study(status="DRAFT")
    study.population_size = None
    use_case = _use_case_with_ready_study(study)

    with pytest.raises(LifecycleError, match="Set a sample size"):
        await use_case.publish(user=Mock(), study_id=study.id)

    use_case._studies.update.assert_not_awaited()


async def test_publish_propagates_create_runs_readiness_errors_unchanged():
    """Publish deliberately duplicates none of create_run's readiness checks —
    a missing analyzed stimulus surfaces the exact same actionable message
    either way, and (per the real transaction) the READY transition made just
    above never commits alongside it."""
    study = _ready_study(status="DRAFT")
    study.population_size = 10
    use_case = _use_case_with_ready_study(study)
    use_case._studies.update.side_effect = _mutate_study_status
    use_case._stimuli.has_analyzed_screens.return_value = False

    with pytest.raises(LifecycleError, match="no analyzed stimulus"):
        await use_case.publish(user=Mock(), study_id=study.id)

    use_case._runs.create_run.assert_not_awaited()


# --- list_runs (item 4/11: run history) ---


async def test_list_runs_pairs_each_run_with_its_completion_rate():
    study = _ready_study()
    use_case = _use_case_with_ready_study(study)
    run_a, run_b = Mock(id=uuid.uuid4()), Mock(id=uuid.uuid4())
    use_case._runs.list_by_study.return_value = [run_a, run_b]
    use_case._results.get_completion_rates.return_value = {run_a.id: 0.72, run_b.id: None}

    rows = await use_case.list_runs(user=Mock(), study_id=study.id)

    assert rows == [
        {"run": run_a, "completion_rate": 0.72},
        {"run": run_b, "completion_rate": None},
    ]
    use_case._results.get_completion_rates.assert_awaited_once_with([run_a.id, run_b.id])


# --- one active run at a time (concurrent-run guard) ---


@pytest.mark.parametrize("active_status", ["PENDING", "RUNNING", "CANCELLING"])
async def test_create_run_rejects_a_second_run_while_one_is_still_active(active_status):
    study = _ready_study()
    use_case = _use_case_with_ready_study(study)
    active_run = Mock(id=uuid.uuid4(), status=active_status)
    use_case._runs.list_by_study.return_value = [active_run]

    with pytest.raises(LifecycleError, match="already has a run in progress"):
        await use_case.create_run(
            user=Mock(), study_id=study.id, population_size=1, task_id=None, config=None, seed=None
        )

    use_case._runs.create_run.assert_not_awaited()


@pytest.mark.parametrize("terminal_status", ["COMPLETED", "FAILED", "CANCELLED"])
async def test_create_run_allows_a_new_run_once_the_prior_one_is_terminal(terminal_status):
    study = _ready_study()
    use_case = _use_case_with_ready_study(study)
    _wire_for_a_runnable_study(use_case, study)
    prior_run = Mock(id=uuid.uuid4(), status=terminal_status)
    use_case._runs.list_by_study.return_value = [prior_run]

    await use_case.create_run(
        user=Mock(), study_id=study.id, population_size=1, task_id=None, config=None, seed=None
    )

    use_case._runs.create_run.assert_awaited_once()


# --- starting_point/success_conditions.screen_key must match a real screen ---


async def test_create_run_rejects_a_starting_point_that_matches_no_real_screen():
    """Reproduced live: a task's starting_point ("Signup Page") didn't match
    any real screen_key (the vision model's own "create_new_account" etc.) —
    resolve_starting_screen silently falls back to an arbitrary screen instead
    of erroring, so every participant started somewhere the researcher never
    intended and the run looked like a UX finding instead of a config typo."""
    study = _ready_study()
    task = TaskModel(
        id=uuid.uuid4(),
        study_id=study.id,
        instruction="Do the thing",
        starting_point="Signup Page",
        success_conditions={"screen_key": "done_screen"},
    )
    use_case = _use_case_with_ready_study(study)
    use_case._stimuli.has_analyzed_screens.return_value = True
    use_case._stimuli.get_screen_graph.return_value = _screen_graph_with(
        "create_new_account", "done_screen"
    )
    use_case._tasks.list_for_study.return_value = [task]

    with pytest.raises(LifecycleError, match="starting_point 'Signup Page'"):
        await use_case.create_run(
            user=Mock(), study_id=study.id, population_size=1, task_id=None, config=None, seed=None
        )

    use_case._runs.create_run.assert_not_awaited()


async def test_create_run_rejects_a_success_screen_key_that_matches_no_real_screen():
    study = _ready_study()
    task = TaskModel(
        id=uuid.uuid4(),
        study_id=study.id,
        instruction="Do the thing",
        success_conditions={"screen_key": "Complete page"},
    )
    use_case = _use_case_with_ready_study(study)
    use_case._stimuli.has_analyzed_screens.return_value = True
    use_case._stimuli.get_screen_graph.return_value = _screen_graph_with("account_created")
    use_case._tasks.list_for_study.return_value = [task]

    with pytest.raises(LifecycleError, match="success_conditions.screen_key 'Complete page'"):
        await use_case.create_run(
            user=Mock(), study_id=study.id, population_size=1, task_id=None, config=None, seed=None
        )

    use_case._runs.create_run.assert_not_awaited()


async def test_create_run_accepts_a_starting_point_and_screen_key_that_both_exist():
    study = _ready_study()
    task = TaskModel(
        id=uuid.uuid4(),
        study_id=study.id,
        instruction="Do the thing",
        starting_point="create_new_account",
        success_conditions={"screen_key": "done_screen"},
    )
    participant = ParticipantRecordModel(id=uuid.uuid4(), audience_id=uuid.uuid4(), traits={})
    use_case = _use_case_with_ready_study(study)
    use_case._stimuli.has_analyzed_screens.return_value = True
    use_case._stimuli.get_screen_graph.return_value = _screen_graph_with(
        "create_new_account", "done_screen"
    )
    use_case._tasks.list_for_study.return_value = [task]
    use_case._audiences.get_latest_for_study.return_value = Mock(id=uuid.uuid4())
    use_case._audiences.list_participants.return_value = [participant]
    use_case._runs.create_run.return_value = Mock(id=uuid.uuid4())
    use_case._runs.create_participant_run.return_value = Mock(id=uuid.uuid4())

    await use_case.create_run(
        user=Mock(), study_id=study.id, population_size=1, task_id=None, config=None, seed=None
    )

    use_case._runs.create_run.assert_awaited_once()
