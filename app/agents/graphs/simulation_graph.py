"""The per-participant Simulation Engine loop (planning/07-simulation-engine.md,
LLD §8 Simulation State Machine): `ORIENT -> PERCEIVE -> ATTEND -> INTERPRET ->
SELECT ACTION -> EXECUTE ACTION -> UPDATE STATE -> CHECK TASK`, looping back to
`PERCEIVE` until a terminal outcome.

Nodes are pure functions of `(state, config)` — `config["configurable"]["deps"]`
carries the injected `ParticipantModel` and the participant's own seeded RNG
(`SimulationDeps`), never state itself, since neither is JSON-shaped data. Both
`attend` and `select_action` sample from the model's returned candidate scores
using that RNG, not the model's own randomness — see
`app/agents/providers/participant_model.py`'s docstring and
`.claude/skills/backend-feature/SKILL.md` §5 for why that split is required for
reproducibility.

No durable checkpointer is wired up: the job handler runs a participant's graph
to completion within a single job attempt, so an in-memory checkpointer would
only protect against a crash *within* that attempt — which the worker's own
retry-the-whole-job behavior (`app/workers/runner.py`) already covers by
re-running `orient` from scratch. Planning/07's "checkpointing for free" note
assumed a durable (Postgres-backed) checkpointer, which is future work if a
single participant's simulation ever needs to survive a worker restart
mid-run.
"""

import math
import random
import uuid
from dataclasses import dataclass
from typing import Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agents.providers.participant_model import (
    ActionCandidate,
    AttentionDecision,
    ParticipantModel,
    ParticipantState,
    SimulationContext,
)
from app.agents.types import ParticipantDraft, ScreenGraph, ScreenView, TaskContext

Outcome = Literal["IN_PROGRESS", "COMPLETED", "FAILED", "ABANDONED"]


class SimulationState(TypedDict):
    participant: ParticipantDraft
    task: TaskContext
    screen_graph: ScreenGraph
    current_screen_id: uuid.UUID
    screen_history: list[uuid.UUID]
    task_progress: float
    confidence: float
    uncertainty: float
    attention_target: uuid.UUID | None
    element_visit_counts: dict[uuid.UUID, int]
    action_history: list[dict]
    dead_end_count: int
    backtrack_count: int
    attention: AttentionDecision | None
    action: ActionCandidate | None
    events: list[dict]
    sequence_no: int
    step: int
    outcome: Outcome
    failure_reason: str | None


@dataclass
class SimulationDeps:
    participant_model: ParticipantModel
    rng: random.Random
    max_steps: int = 40


def _deps(config: RunnableConfig) -> SimulationDeps:
    return config["configurable"]["deps"]


def _make_event(
    sequence_no: int,
    *,
    type_: str,
    screen_id: uuid.UUID | None = None,
    element_id: uuid.UUID | None = None,
    x: float | None = None,
    y: float | None = None,
    duration_ms: int | None = None,
    payload: dict | None = None,
) -> dict:
    return {
        "sequence_no": sequence_no,
        "type": type_,
        "screen_id": screen_id,
        "element_id": element_id,
        "x": x,
        "y": y,
        "duration_ms": duration_ms,
        "payload": payload,
    }


def _sample_point_in_bbox(
    bbox: tuple[int, int, int, int], rng: random.Random
) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (rng.uniform(x1, x2), rng.uniform(y1, y2))


def _softmax_sample(items: list, scores: list[float], rng: random.Random, temperature: float = 4.0):
    """Converts candidate scores into a probability distribution and samples
    from it (LLD §9's explicit requirement) — the model only supplies scores."""
    if not items:
        return None
    max_score = max(scores)
    weights = [math.exp((score - max_score) * temperature) for score in scores]
    total = sum(weights)
    probabilities = [weight / total for weight in weights]
    draw = rng.random()
    cumulative = 0.0
    for item, probability in zip(items, probabilities, strict=True):
        cumulative += probability
        if draw <= cumulative:
            return item
    return items[-1]


def _build_context(state: SimulationState, screen: ScreenView) -> SimulationContext:
    return SimulationContext(
        participant=state["participant"],
        task=state["task"],
        screen=screen,
        state=ParticipantState(
            current_screen_id=state["current_screen_id"],
            task_progress=state["task_progress"],
            confidence=state["confidence"],
            uncertainty=state["uncertainty"],
            attention_target=state["attention_target"],
            element_visit_counts=state["element_visit_counts"],
            action_history=state["action_history"],
            dead_end_count=state["dead_end_count"],
            backtrack_count=state["backtrack_count"],
        ),
        attention=state.get("attention"),
    )


def _element_semantic_role(screen_graph: ScreenGraph, target: str | None) -> str | None:
    if not target:
        return None
    element_id = uuid.UUID(target)
    for screen in screen_graph.screens.values():
        element = screen.element(element_id)
        if element is not None:
            return element.semantic_role
    return None


async def orient(state: SimulationState, config: RunnableConfig) -> dict:
    sequence_no = state["sequence_no"]
    event = _make_event(sequence_no, type_="SCREEN_ENTER", screen_id=state["current_screen_id"])
    return {
        "events": [*state["events"], event],
        "sequence_no": sequence_no + 1,
        "outcome": "IN_PROGRESS",
    }


async def perceive(state: SimulationState, config: RunnableConfig) -> dict:
    if state["current_screen_id"] not in state["screen_graph"].screens:
        return {"outcome": "FAILED", "failure_reason": "screen_not_found"}
    return {}


def _route_after_perceive(state: SimulationState) -> str:
    return "terminal" if state["outcome"] != "IN_PROGRESS" else "continue"


async def attend(state: SimulationState, config: RunnableConfig) -> dict:
    deps = _deps(config)
    screen = state["screen_graph"].screens[state["current_screen_id"]]
    context = _build_context(state, screen)
    decision = await deps.participant_model.select_attention(context)

    sampled = _softmax_sample(
        decision.candidates, [c.attention_score for c in decision.candidates], deps.rng
    )
    events = list(state["events"])
    visit_counts = dict(state["element_visit_counts"])
    sequence_no = state["sequence_no"]
    attention_target = state["attention_target"]

    if sampled is not None:
        element_id = uuid.UUID(sampled.element_id)
        element = screen.element(element_id)
        attention_target = element_id
        visit_counts[element_id] = visit_counts.get(element_id, 0) + 1
        x, y = (
            _sample_point_in_bbox(element.bbox, deps.rng) if element is not None else (None, None)
        )
        events.append(
            _make_event(
                sequence_no,
                type_="GAZE",
                screen_id=screen.id,
                element_id=element_id,
                x=x,
                y=y,
                duration_ms=int(deps.rng.uniform(180, 900)),
                payload={"attention_score": sampled.attention_score},
            )
        )
        sequence_no += 1

    return {
        "attention": decision,
        "attention_target": attention_target,
        "element_visit_counts": visit_counts,
        "events": events,
        "sequence_no": sequence_no,
    }


async def interpret(state: SimulationState, config: RunnableConfig) -> dict:
    """Deterministic merge (LLD §8's INTERPRET state) — no model call. Attention
    that's spread evenly across candidates (nothing stands out) raises
    uncertainty for the upcoming action-selection step; a clear standout
    lowers it."""
    candidates = state["attention"].candidates if state["attention"] else []
    if candidates:
        scores = [c.attention_score for c in candidates]
        spread = max(scores) - (sum(scores) / len(scores))
        uncertainty = max(0.0, min(1.0, 0.6 - spread))
    else:
        uncertainty = min(1.0, state["uncertainty"] + 0.1)
    return {"uncertainty": uncertainty, "confidence": max(0.0, min(1.0, 1.0 - uncertainty))}


async def select_action(state: SimulationState, config: RunnableConfig) -> dict:
    deps = _deps(config)
    screen = state["screen_graph"].screens[state["current_screen_id"]]
    context = _build_context(state, screen)
    decision = await deps.participant_model.select_action(context)
    chosen = _softmax_sample(
        decision.candidates, [c.utility for c in decision.candidates], deps.rng
    )
    return {"action": chosen}


async def execute_action(state: SimulationState, config: RunnableConfig) -> dict:
    deps = _deps(config)
    action = state["action"]
    screen_graph = state["screen_graph"]
    current_screen_id = state["current_screen_id"]
    screen = screen_graph.screens[current_screen_id]

    element_id = uuid.UUID(action.target) if action.target else None
    element = screen.element(element_id) if element_id is not None else None
    x, y = _sample_point_in_bbox(element.bbox, deps.rng) if element is not None else (None, None)

    events = list(state["events"])
    sequence_no = state["sequence_no"]
    events.append(
        _make_event(
            sequence_no,
            type_=action.action,
            screen_id=current_screen_id,
            element_id=element_id,
            x=x,
            y=y,
            payload={"confidence": action.confidence, "utility": action.utility},
        )
    )
    sequence_no += 1

    screen_history = list(state["screen_history"])
    dead_end_count = state["dead_end_count"]
    backtrack_count = state["backtrack_count"]
    new_screen_id = current_screen_id

    if action.action == "BACK":
        if screen_history:
            new_screen_id = screen_history.pop()
            backtrack_count += 1
    elif element_id is not None and action.action in ("CLICK", "TAP", "OPEN", "SELECT"):
        transition = next(
            (
                t
                for t in screen_graph.transitions_from(current_screen_id)
                if t.trigger_element_id == element_id
            ),
            None,
        )
        if transition is not None:
            screen_history.append(current_screen_id)
            new_screen_id = transition.to_screen_id
        else:
            dead_end_count += 1

    if new_screen_id != current_screen_id:
        events.append(_make_event(sequence_no, type_="SCREEN_EXIT", screen_id=current_screen_id))
        sequence_no += 1
        events.append(_make_event(sequence_no, type_="SCREEN_ENTER", screen_id=new_screen_id))
        sequence_no += 1

    action_history = [
        *state["action_history"],
        {"action": action.action, "target": action.target, "step": state["step"]},
    ]

    return {
        "events": events,
        "action_history": action_history,
        "current_screen_id": new_screen_id,
        "screen_history": screen_history,
        "dead_end_count": dead_end_count,
        "backtrack_count": backtrack_count,
        "sequence_no": sequence_no,
        "step": state["step"] + 1,
    }


async def update_state(state: SimulationState, config: RunnableConfig) -> dict:
    """LLD §12 Task Evaluation's progress computation — matches consumed
    elements against `task.expected_critical_actions`, falling back to a
    generic exploration signal when a task doesn't declare any."""
    screen_graph = state["screen_graph"]
    critical = set(state["task"].expected_critical_actions or [])

    if critical:
        matched: set[str] = set()
        for entry in state["action_history"]:
            target = entry.get("target")
            if not target:
                continue
            element_id = uuid.UUID(target)
            element = next(
                (
                    s.element(element_id)
                    for s in screen_graph.screens.values()
                    if s.element(element_id)
                ),
                None,
            )
            if element is None:
                continue
            matched |= {element.element_key, element.semantic_role or ""} & critical
        progress = len(matched) / len(critical)
    else:
        primary_action_clicked = any(
            entry.get("action") in ("CLICK", "TAP", "SELECT")
            and _element_semantic_role(screen_graph, entry.get("target")) == "primary_action"
            for entry in state["action_history"]
        )
        distinct_screens = len(set(state["screen_history"]) | {state["current_screen_id"]})
        progress = 1.0 if primary_action_clicked else min(0.9, 0.15 * distinct_screens)

    events = list(state["events"])
    sequence_no = state["sequence_no"]
    if abs(progress - state["task_progress"]) > 0.01:
        events.append(
            _make_event(sequence_no, type_="TASK_PROGRESS", payload={"progress": progress})
        )
        sequence_no += 1

    return {"task_progress": progress, "events": events, "sequence_no": sequence_no}


async def check_task(state: SimulationState, config: RunnableConfig) -> dict:
    """LLD §12 terminal-state decision. `perceive` already routes a missing
    screen straight to END, so `state["outcome"]` here is always still
    `IN_PROGRESS` on entry."""
    deps = _deps(config)
    events = list(state["events"])
    sequence_no = state["sequence_no"]
    outcome: Outcome = "IN_PROGRESS"
    failure_reason: str | None = None

    if state["task_progress"] >= 1.0:
        outcome = "COMPLETED"
        events.append(_make_event(sequence_no, type_="TASK_SUCCESS", payload={"progress": 1.0}))
        sequence_no += 1
    elif state["step"] >= deps.max_steps:
        outcome, failure_reason = "ABANDONED", "max_steps_exceeded"
        events.append(_make_event(sequence_no, type_="ABANDON", payload={"reason": failure_reason}))
        sequence_no += 1
    else:
        screen = state["screen_graph"].screens[state["current_screen_id"]]
        stuck = not any(e.interactable for e in screen.elements) and not state["screen_history"]
        if stuck:
            outcome, failure_reason = "FAILED", "dead_end_no_actions"
            events.append(
                _make_event(sequence_no, type_="TASK_FAILURE", payload={"reason": failure_reason})
            )
            sequence_no += 1
        else:
            patience = state["participant"].traits.get("patience", 0.5)
            abandon_pressure = state["uncertainty"] * (1 - patience) + 0.1 * min(
                1.0, state["dead_end_count"] / 4
            )
            if abandon_pressure > 0.75 and state["step"] > 5:
                outcome, failure_reason = "ABANDONED", "low_patience_high_uncertainty"
                events.append(
                    _make_event(sequence_no, type_="ABANDON", payload={"reason": failure_reason})
                )
                sequence_no += 1

    return {
        "outcome": outcome,
        "failure_reason": failure_reason,
        "events": events,
        "sequence_no": sequence_no,
    }


def _route_after_check_task(state: SimulationState) -> str:
    return "continue" if state["outcome"] == "IN_PROGRESS" else "terminal"


def _build_graph():
    graph = StateGraph(SimulationState)
    graph.add_node("orient", orient)
    graph.add_node("perceive", perceive)
    graph.add_node("attend", attend)
    graph.add_node("interpret", interpret)
    graph.add_node("select_action", select_action)
    graph.add_node("execute_action", execute_action)
    graph.add_node("update_state", update_state)
    graph.add_node("check_task", check_task)

    graph.add_edge(START, "orient")
    graph.add_edge("orient", "perceive")
    graph.add_conditional_edges(
        "perceive", _route_after_perceive, {"continue": "attend", "terminal": END}
    )
    graph.add_edge("attend", "interpret")
    graph.add_edge("interpret", "select_action")
    graph.add_edge("select_action", "execute_action")
    graph.add_edge("execute_action", "update_state")
    graph.add_edge("update_state", "check_task")
    graph.add_conditional_edges(
        "check_task", _route_after_check_task, {"continue": "perceive", "terminal": END}
    )
    return graph.compile()


_COMPILED_GRAPH = _build_graph()


async def run_simulation(
    *,
    participant: ParticipantDraft,
    task: TaskContext,
    screen_graph: ScreenGraph,
    starting_screen_id: uuid.UUID,
    seed: int | str | None,
    participant_model: ParticipantModel,
    max_steps: int = 40,
) -> SimulationState:
    deps = SimulationDeps(
        participant_model=participant_model, rng=random.Random(seed), max_steps=max_steps
    )
    initial_state: SimulationState = {
        "participant": participant,
        "task": task,
        "screen_graph": screen_graph,
        "current_screen_id": starting_screen_id,
        "screen_history": [],
        "task_progress": 0.0,
        "confidence": 0.5,
        "uncertainty": 0.3,
        "attention_target": None,
        "element_visit_counts": {},
        "action_history": [],
        "dead_end_count": 0,
        "backtrack_count": 0,
        "attention": None,
        "action": None,
        "events": [],
        "sequence_no": 0,
        "step": 0,
        "outcome": "IN_PROGRESS",
        "failure_reason": None,
    }
    config = {"configurable": {"deps": deps}, "recursion_limit": max_steps * 8 + 20}
    return await _COMPILED_GRAPH.ainvoke(initial_state, config=config)
