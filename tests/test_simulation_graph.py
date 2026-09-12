import uuid

import pytest

from app.agents.graphs.simulation_graph import (
    MAX_SCAN_ATTEMPTS,
    _scan_duration_range_ms,
    run_simulation,
)
from app.agents.providers.participant_model import (
    ActionDecision,
    AttentionCandidate,
    AttentionDecision,
    HeuristicParticipantModel,
    RandomParticipantModel,
    SaliencyOnlyParticipantModel,
    TaskOnlyParticipantModel,
    get_participant_model,
)
from app.agents.types import (
    ElementView,
    ParticipantDraft,
    ScreenGraph,
    ScreenView,
    TaskContext,
    TransitionView,
)

HOME_ID = uuid.uuid4()
CONFIRM_ID = uuid.uuid4()
SEARCH_ID = uuid.uuid4()
CTA_ID = uuid.uuid4()
HELP_ID = uuid.uuid4()
SUCCESS_ID = uuid.uuid4()

LAUNCH_ID = uuid.uuid4()
MIDDLE_ID = uuid.uuid4()
FINAL_ID = uuid.uuid4()
LAUNCH_CTA_ID = uuid.uuid4()
MIDDLE_CTA_ID = uuid.uuid4()


def _shoe_task_screen_graph() -> ScreenGraph:
    home = ScreenView(
        id=HOME_ID,
        screen_key="home",
        width=390,
        height=844,
        elements=[
            ElementView(
                id=SEARCH_ID,
                element_key="search",
                type="input",
                text="Search shoes",
                bbox=(20, 30, 370, 82),
                semantic_role="search",
                interactable=True,
            ),
            ElementView(
                id=CTA_ID,
                element_key="cta",
                type="button",
                text="Add running shoe to cart",
                bbox=(20, 720, 370, 776),
                semantic_role="primary_action",
                interactable=True,
            ),
            ElementView(
                id=HELP_ID,
                element_key="help",
                type="link",
                text="Need help?",
                bbox=(20, 800, 150, 830),
                semantic_role="help",
                interactable=True,
            ),
        ],
    )
    confirm = ScreenView(
        id=CONFIRM_ID,
        screen_key="confirm",
        width=390,
        height=844,
        elements=[
            ElementView(
                id=SUCCESS_ID,
                element_key="added_confirmation",
                type="text",
                text="Added to cart",
                bbox=(20, 100, 370, 150),
                semantic_role="confirmation",
                interactable=False,
            )
        ],
    )
    transitions = [
        TransitionView(
            from_screen_id=HOME_ID,
            trigger_element_id=CTA_ID,
            action="CLICK",
            to_screen_id=CONFIRM_ID,
        )
    ]
    return ScreenGraph(screens={HOME_ID: home, CONFIRM_ID: confirm}, transitions=transitions)


def _multi_screen_onboarding_graph() -> ScreenGraph:
    """launch -> middle -> final, where BOTH launch and middle carry their own
    'primary_action'-role button — reproduces the exact regression this file's
    new tests below guard against: a critical-action list naming a shared
    *role* (not a specific element) used to let the very first click, on the
    very first screen, complete the whole task."""
    launch = ScreenView(
        id=LAUNCH_ID,
        screen_key="launch",
        width=390,
        height=844,
        elements=[
            ElementView(
                id=LAUNCH_CTA_ID,
                element_key="create_account_button",
                type="button",
                text="Create an account",
                bbox=(20, 300, 370, 360),
                semantic_role="primary_action",
                interactable=True,
            )
        ],
    )
    middle = ScreenView(
        id=MIDDLE_ID,
        screen_key="middle",
        width=390,
        height=844,
        elements=[
            ElementView(
                id=MIDDLE_CTA_ID,
                element_key="continue_button",
                type="button",
                text="Continue",
                bbox=(20, 300, 370, 360),
                semantic_role="primary_action",
                interactable=True,
            )
        ],
    )
    final = ScreenView(id=FINAL_ID, screen_key="final", width=390, height=844, elements=[])
    transitions = [
        TransitionView(
            from_screen_id=LAUNCH_ID,
            trigger_element_id=LAUNCH_CTA_ID,
            action="CLICK",
            to_screen_id=MIDDLE_ID,
        ),
        TransitionView(
            from_screen_id=MIDDLE_ID,
            trigger_element_id=MIDDLE_CTA_ID,
            action="CLICK",
            to_screen_id=FINAL_ID,
        ),
    ]
    return ScreenGraph(
        screens={LAUNCH_ID: launch, MIDDLE_ID: middle, FINAL_ID: final}, transitions=transitions
    )


def _participant(**trait_overrides: float) -> ParticipantDraft:
    traits = {
        "digital_confidence": 0.6,
        "product_familiarity": 0.5,
        "exploration": 0.5,
        "patience": 0.6,
        "goal_directedness": 0.7,
        **trait_overrides,
    }
    return ParticipantDraft(id=uuid.uuid4(), traits=traits)


def _task() -> TaskContext:
    return TaskContext(
        id=uuid.uuid4(),
        instruction="Add a running shoe under 5000 to cart",
        starting_point="home",
        success_conditions=None,
        constraints=None,
        expected_critical_actions=["cta"],
    )


@pytest.mark.parametrize(
    "model_cls",
    [
        HeuristicParticipantModel,
        RandomParticipantModel,
        SaliencyOnlyParticipantModel,
        TaskOnlyParticipantModel,
    ],
)
async def test_reaches_a_terminal_outcome_for_every_participant_model(model_cls):
    screen_graph = _shoe_task_screen_graph()
    task = _task()
    participant = _participant()

    result = await run_simulation(
        participant=participant,
        task=task,
        screen_graph=screen_graph,
        starting_screen_id=screen_graph.resolve_starting_screen(task.starting_point),
        seed=42,
        participant_model=model_cls(),
        max_steps=20,
    )

    assert result["outcome"] in ("COMPLETED", "FAILED", "ABANDONED")
    assert result["events"], "a run must emit at least one observation event"
    assert result["events"][0]["type"] == "SCREEN_ENTER"


async def test_heuristic_model_completes_the_task_by_clicking_the_critical_action():
    screen_graph = _shoe_task_screen_graph()
    task = _task()
    participant = _participant(goal_directedness=0.9, exploration=0.2)

    result = await run_simulation(
        participant=participant,
        task=task,
        screen_graph=screen_graph,
        starting_screen_id=screen_graph.resolve_starting_screen(task.starting_point),
        seed=7,
        participant_model=HeuristicParticipantModel(),
        max_steps=30,
    )

    assert result["outcome"] == "COMPLETED"
    assert result["task_progress"] == 1.0
    assert any(e["type"] == "CLICK" and e["element_id"] == CTA_ID for e in result["events"])
    assert result["current_screen_id"] == CONFIRM_ID


async def test_same_participant_and_seed_is_reproducible():
    screen_graph = _shoe_task_screen_graph()
    task = _task()
    participant = _participant()
    starting = screen_graph.resolve_starting_screen(task.starting_point)

    async def run():
        return await run_simulation(
            participant=participant,
            task=task,
            screen_graph=screen_graph,
            starting_screen_id=starting,
            seed=123,
            participant_model=HeuristicParticipantModel(),
            max_steps=20,
        )

    first, second = await run(), await run()

    assert first["outcome"] == second["outcome"]
    assert [e["type"] for e in first["events"]] == [e["type"] for e in second["events"]]
    assert [e["element_id"] for e in first["events"]] == [e["element_id"] for e in second["events"]]


async def test_different_seeds_can_produce_different_scanpaths():
    screen_graph = _shoe_task_screen_graph()
    task = _task()
    participant = _participant(goal_directedness=0.4, exploration=0.8)

    outcomes = set()
    for seed in range(10):
        result = await run_simulation(
            participant=participant,
            task=task,
            screen_graph=screen_graph,
            starting_screen_id=screen_graph.resolve_starting_screen(task.starting_point),
            seed=seed,
            participant_model=HeuristicParticipantModel(),
            max_steps=20,
        )
        gaze_sequence = tuple(e["element_id"] for e in result["events"] if e["type"] == "GAZE")
        outcomes.add(gaze_sequence)

    assert (
        len(outcomes) > 1
    ), "stochastic sampling should produce more than one scanpath across seeds"


def test_get_participant_model_defaults_to_heuristic():
    assert isinstance(get_participant_model(None), HeuristicParticipantModel)
    assert isinstance(get_participant_model("unknown"), HeuristicParticipantModel)
    assert isinstance(get_participant_model("random"), RandomParticipantModel)


async def test_a_shared_role_critical_action_cannot_complete_a_task_from_the_first_screen():
    """Regression test for the exact bug reported: `expected_critical_actions`
    naming a *role* shared by every screen's own primary CTA (not a specific
    element) used to let the very first click, on the very first screen,
    mark task_progress=1.0 and the run COMPLETED in a single step — before
    ever reaching the task's actual success screen. With a recognized
    success_condition defined, critical actions are milestones only (capped
    at 0.99); the task can only ever complete by genuinely reaching `final`."""
    screen_graph = _multi_screen_onboarding_graph()
    task = TaskContext(
        id=uuid.uuid4(),
        instruction="Create a new account",
        starting_point="launch",
        success_conditions={"screen_key": "final"},
        constraints=None,
        expected_critical_actions=["primary_action"],
    )
    participant = _participant(goal_directedness=0.9, exploration=0.2)

    result = await run_simulation(
        participant=participant,
        task=task,
        screen_graph=screen_graph,
        starting_screen_id=screen_graph.resolve_starting_screen(task.starting_point),
        seed=7,
        participant_model=HeuristicParticipantModel(),
        max_steps=20,
    )

    assert not (
        result["step"] == 1 and result["outcome"] == "COMPLETED"
    ), "clicking the launch screen's primary action alone must not complete the task"
    if result["outcome"] == "COMPLETED":
        assert result["current_screen_id"] == FINAL_ID
        assert result["step"] >= 2, "reaching the final screen requires at least 2 clicks"
        assert result["task_progress"] == 1.0


async def test_no_success_condition_or_critical_actions_never_fabricates_completion():
    """The other half of the same bug: with neither success_conditions nor
    expected_critical_actions defined at all, clicking a primary_action
    element used to unconditionally set task_progress=1.0. There is no
    genuine completion signal in this configuration, so the task must never
    report COMPLETED — only a real terminal state (ABANDONED/FAILED) once the
    participant gives up or runs out of steps, i.e. a drop-off."""
    screen_graph = _multi_screen_onboarding_graph()
    task = TaskContext(
        id=uuid.uuid4(),
        instruction="Explore the app",
        starting_point="launch",
        success_conditions=None,
        constraints=None,
        expected_critical_actions=None,
    )
    participant = _participant(goal_directedness=0.9, exploration=0.2)

    result = await run_simulation(
        participant=participant,
        task=task,
        screen_graph=screen_graph,
        starting_screen_id=screen_graph.resolve_starting_screen(task.starting_point),
        seed=7,
        participant_model=HeuristicParticipantModel(),
        max_steps=15,
    )

    assert result["outcome"] != "COMPLETED"
    assert result["task_progress"] < 1.0


async def test_unrecognized_success_conditions_shape_does_not_block_critical_actions():
    """A freeform success_conditions dict using none of the recognized keys
    (screen_key/element_key/semantic_role) — planning/12-web-app.md's own
    example, {"beneficiary_credited": true} — has no defined evaluation
    semantics anywhere in this codebase, so it must not silently block a
    task that otherwise fully satisfies its own expected_critical_actions
    from ever completing (falls back to the pre-existing, tested contract)."""
    screen_graph = _shoe_task_screen_graph()
    task = TaskContext(
        id=uuid.uuid4(),
        instruction="Add a running shoe under 5000 to cart",
        starting_point="home",
        success_conditions={"beneficiary_credited": True},
        constraints=None,
        expected_critical_actions=["cta"],
    )
    participant = _participant(goal_directedness=0.9, exploration=0.2)

    result = await run_simulation(
        participant=participant,
        task=task,
        screen_graph=screen_graph,
        starting_screen_id=screen_graph.resolve_starting_screen(task.starting_point),
        seed=7,
        participant_model=HeuristicParticipantModel(),
        max_steps=30,
    )

    assert result["outcome"] == "COMPLETED"
    assert result["task_progress"] == 1.0


# --- Scan-gated attention/action coupling ------------------------------------------
# A screen with a resolvable "intended element" (task.expected_critical_actions
# present on that screen) gates action on attention discovering it first — see
# app/agents/graphs/simulation_graph.py's module docstring and
# _intended_element_for_screen.

SCAN_SCREEN_ID = uuid.uuid4()
NEXT_SCREEN_ID = uuid.uuid4()
INTENDED_ID = uuid.uuid4()
DISTRACTOR_ID = uuid.uuid4()


def _scan_test_screen_graph() -> ScreenGraph:
    scan_screen = ScreenView(
        id=SCAN_SCREEN_ID,
        screen_key="scan_screen",
        width=390,
        height=844,
        elements=[
            ElementView(
                id=INTENDED_ID,
                element_key="intended_button",
                type="button",
                text="Continue",
                bbox=(20, 300, 370, 360),
                semantic_role="primary_action",
                interactable=True,
            ),
            ElementView(
                id=DISTRACTOR_ID,
                element_key="distractor_link",
                type="link",
                text="Learn more",
                bbox=(20, 400, 370, 430),
                semantic_role="help",
                interactable=True,
            ),
        ],
    )
    next_screen = ScreenView(
        id=NEXT_SCREEN_ID, screen_key="next_screen", width=390, height=844, elements=[]
    )
    transitions = [
        TransitionView(
            from_screen_id=SCAN_SCREEN_ID,
            trigger_element_id=INTENDED_ID,
            action="CLICK",
            to_screen_id=NEXT_SCREEN_ID,
        )
    ]
    return ScreenGraph(
        screens={SCAN_SCREEN_ID: scan_screen, NEXT_SCREEN_ID: next_screen}, transitions=transitions
    )


def _scan_task() -> TaskContext:
    return TaskContext(
        id=uuid.uuid4(),
        instruction="Continue",
        starting_point="scan_screen",
        success_conditions={"screen_key": "next_screen"},
        constraints=None,
        expected_critical_actions=["intended_button"],
    )


class _FixedAttentionModel:
    """Always attends to exactly one, fixed element_id, regardless of screen
    or persona — makes the scan-gating tests below fully deterministic
    instead of relying on softmax probabilities ever landing (or never
    landing) on a target."""

    def __init__(self, always_attends_to: uuid.UUID):
        self._target = always_attends_to

    async def select_attention(self, context):
        return AttentionDecision(
            candidates=[
                AttentionCandidate(
                    element_id=str(self._target),
                    visual_saliency=1.0,
                    task_relevance=1.0,
                    persona_relevance=1.0,
                    state_relevance=1.0,
                    attention_score=1.0,
                )
            ]
        )

    async def select_action(self, context):
        return ActionDecision(candidates=[])


async def test_exhausting_scan_attempts_without_finding_the_intended_element_is_a_dropoff():
    screen_graph = _scan_test_screen_graph()
    task = _scan_task()
    participant = _participant()

    result = await run_simulation(
        participant=participant,
        task=task,
        screen_graph=screen_graph,
        starting_screen_id=screen_graph.resolve_starting_screen(task.starting_point),
        seed=1,
        participant_model=_FixedAttentionModel(always_attends_to=DISTRACTOR_ID),
        max_steps=20,
    )

    assert result["outcome"] == "ABANDONED"
    assert result["failure_reason"] == "intended_action_not_discovered"
    assert result["current_screen_id"] == SCAN_SCREEN_ID, "must never have transitioned"
    assert result["scan_count"] == MAX_SCAN_ATTEMPTS
    gaze_events = [e for e in result["events"] if e["type"] == "GAZE"]
    assert len(gaze_events) == MAX_SCAN_ATTEMPTS
    assert all(e["element_id"] == DISTRACTOR_ID for e in gaze_events)


async def test_finding_the_intended_element_on_the_first_scan_acts_on_it_immediately():
    screen_graph = _scan_test_screen_graph()
    task = _scan_task()
    participant = _participant()

    result = await run_simulation(
        participant=participant,
        task=task,
        screen_graph=screen_graph,
        starting_screen_id=screen_graph.resolve_starting_screen(task.starting_point),
        seed=1,
        participant_model=_FixedAttentionModel(always_attends_to=INTENDED_ID),
        max_steps=20,
    )

    assert result["outcome"] == "COMPLETED"
    assert result["current_screen_id"] == NEXT_SCREEN_ID
    gaze_events = [e for e in result["events"] if e["type"] == "GAZE"]
    assert gaze_events[0]["payload"]["scan_number"] == 1
    assert any(e["type"] == "CLICK" and e["element_id"] == INTENDED_ID for e in result["events"])


async def test_a_screen_with_no_resolvable_intended_element_is_unaffected_by_scan_gating():
    """The shoe-task fixture's `confirm` screen has zero elements and no
    critical-action overlap — scan-gating must never engage there, and the
    original interpret->select_action flow (already exercised by the older
    tests above) must be what actually runs."""
    screen_graph = _shoe_task_screen_graph()
    task = TaskContext(
        id=uuid.uuid4(),
        instruction="Add a running shoe under 5000 to cart",
        starting_point="confirm",
        success_conditions=None,
        constraints=None,
        expected_critical_actions=["cta"],
    )
    participant = _participant()

    result = await run_simulation(
        participant=participant,
        task=task,
        screen_graph=screen_graph,
        starting_screen_id=screen_graph.resolve_starting_screen(task.starting_point),
        seed=1,
        participant_model=HeuristicParticipantModel(),
        max_steps=10,
    )

    assert result["outcome"] in ("FAILED", "ABANDONED")
    assert result["failure_reason"] != "intended_action_not_discovered"


def test_scan_duration_is_faster_for_a_confident_familiar_persona():
    """Regression test: duration_ms on a GAZE event used to be a fixed
    180-900ms window for every persona, ignoring digital_confidence/
    product_familiarity entirely."""
    fast_low, fast_high = _scan_duration_range_ms(
        {"digital_confidence": 1.0, "product_familiarity": 1.0}
    )
    slow_low, slow_high = _scan_duration_range_ms(
        {"digital_confidence": 0.0, "product_familiarity": 0.0}
    )

    assert fast_low < slow_low
    assert fast_high < slow_high


def test_scan_duration_defaults_to_the_mid_range_when_traits_are_missing():
    low, high = _scan_duration_range_ms({})
    assert 150 <= low <= 400
    assert 500 <= high <= 1400
