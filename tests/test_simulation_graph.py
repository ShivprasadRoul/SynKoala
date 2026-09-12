import uuid

import pytest

from app.agents.graphs.simulation_graph import run_simulation
from app.agents.providers.participant_model import (
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
