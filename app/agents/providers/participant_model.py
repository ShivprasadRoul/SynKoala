"""LLD §28 `ParticipantModel` protocol, plus concrete implementations
(planning/07-simulation-engine.md).

`select_attention`/`select_action` return **scores per candidate**, not a
probability distribution and not a single pick — converting scores into a
distribution and sampling from it is the calling LangGraph node's job
(`app/agents/graphs/simulation_graph.py`), using the participant's own seeded
RNG. That split is what keeps a given participant+seed reproducible
independent of anything a model-backed implementation does internally
(`.claude/skills/backend-feature/SKILL.md` §5).

`HeuristicParticipantModel` is the concrete LLD §9-§11 implementation for now
— it computes the four named factors (visual saliency, task relevance,
persona relevance, state relevance) from the screen/task/persona data itself,
with no external model call. Swapping to `PydanticAIParticipantModel` (a
hosted-model-backed implementation behind this same protocol) is future work
gated on model credentials existing (`CLAUDE.md` "Repository state") — the
Protocol is what makes that swap not touch any caller.

The three baseline models exist for the Validation Engine's required baseline
comparisons (`04-Evaluation-Spec-Synthetic-Koala.md` §6) — same protocol, no
model call, trivial scoring.
"""

import re
import uuid
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

from app.agents.types import ElementView, ParticipantDraft, ScreenView, TaskContext

ActionType = Literal["CLICK", "SCROLL", "BACK", "OPEN", "SELECT", "TYPE"]


class AttentionCandidate(BaseModel):
    element_id: str
    visual_saliency: float
    task_relevance: float
    persona_relevance: float
    state_relevance: float
    attention_score: float


class AttentionDecision(BaseModel):
    candidates: list[AttentionCandidate]


class ActionCandidate(BaseModel):
    action: ActionType
    target: str | None
    utility: float
    confidence: float


class ActionDecision(BaseModel):
    candidates: list[ActionCandidate]


class ParticipantState(BaseModel):
    current_screen_id: uuid.UUID
    task_progress: float
    confidence: float
    uncertainty: float
    attention_target: uuid.UUID | None
    element_visit_counts: dict[uuid.UUID, int]
    action_history: list[dict]
    dead_end_count: int
    backtrack_count: int


class SimulationContext(BaseModel):
    participant: ParticipantDraft
    task: TaskContext
    screen: ScreenView
    state: ParticipantState
    attention: AttentionDecision | None = None


@runtime_checkable
class ParticipantModel(Protocol):
    async def select_attention(self, context: SimulationContext) -> AttentionDecision: ...

    async def select_action(self, context: SimulationContext) -> ActionDecision: ...


def _tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    return {token for token in re.split(r"[^a-z0-9]+", text.lower()) if token}


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def _default_action_for(element: ElementView) -> ActionType:
    if element.type == "input":
        return "TYPE"
    if element.type == "select" or element.semantic_role in ("select", "option"):
        return "SELECT"
    return "CLICK"


def _visual_saliency(element: ElementView, screen: ScreenView) -> float:
    x1, y1, x2, y2 = element.bbox
    area = max(1, (x2 - x1) * (y2 - y1))
    viewport_area = max(1, (screen.width or 390) * (screen.height or 844))
    area_ratio = min(1.0, area / viewport_area)
    vertical_center = (y1 + y2) / 2
    # elements near the top of the viewport get scanned first (fold bias)
    fold_bias = 1.0 - 0.4 * min(1.0, vertical_center / max(1, screen.height or 844))
    type_bonus = {"button": 0.15, "image": 0.1, "input": 0.05}.get(element.type, 0.0)
    role_bonus = 0.15 if element.semantic_role == "primary_action" else 0.0
    return _clip((0.25 + 0.5 * area_ratio + type_bonus + role_bonus) * fold_bias)


def _task_relevance(element: ElementView, task: TaskContext) -> float:
    element_tokens = (
        _tokenize(element.text) | _tokenize(element.semantic_role) | _tokenize(element.element_key)
    )
    if not element_tokens:
        return 0.1
    instruction_overlap = len(element_tokens & _tokenize(task.instruction)) / len(element_tokens)
    critical_tokens: set[str] = set()
    for action in task.expected_critical_actions or []:
        critical_tokens |= _tokenize(action)
    critical_overlap = (
        len(element_tokens & critical_tokens) / len(element_tokens) if critical_tokens else 0.0
    )
    role_bonus = 0.25 if element.semantic_role == "primary_action" else 0.0
    return _clip(0.15 + 0.35 * instruction_overlap + 0.5 * critical_overlap + role_bonus)


def _persona_relevance(element: ElementView, traits: dict[str, float]) -> float:
    exploration = traits.get("exploration", 0.5)
    goal_directedness = traits.get("goal_directedness", 0.5)
    familiarity = traits.get("product_familiarity", 0.5)
    role = element.semantic_role or ""
    if role == "primary_action":
        base = 0.4 + 0.5 * goal_directedness
    elif role in ("navigation", "help", "info"):
        base = 0.5 * exploration * (1.0 - 0.5 * familiarity) + 0.15
    else:
        base = 0.3 + 0.4 * exploration
    return _clip(base)


def _state_relevance(element: ElementView, state: ParticipantState) -> float:
    visits = state.element_visit_counts.get(element.id, 0)
    habituation_penalty = min(0.6, 0.2 * visits)
    continuity_bonus = 0.2 if element.id == state.attention_target else 0.0
    return _clip(0.5 + continuity_bonus - habituation_penalty)


def _attention_weights(traits: dict[str, float]) -> dict[str, float]:
    goal_directedness = traits.get("goal_directedness", 0.5)
    exploration = traits.get("exploration", 0.5)
    return {
        "visual": 0.25 + 0.15 * exploration,
        "task": 0.25 + 0.35 * goal_directedness,
        "persona": 0.2,
        "state": 0.15,
    }


def _repeat_penalty(state: ParticipantState, action: ActionType, element_id: uuid.UUID) -> float:
    repeats = 0
    for entry in reversed(state.action_history):
        if entry.get("action") == action and entry.get("target") == str(element_id):
            repeats += 1
        else:
            break
    return min(0.6, 0.25 * repeats)


def _action_utility(
    action: ActionType,
    attention_score: float,
    task_relevance: float,
    traits: dict[str, float],
    state: ParticipantState,
    repeat_penalty: float,
) -> float:
    patience = traits.get("patience", 0.5)
    goal_directedness = traits.get("goal_directedness", 0.5)
    base = 0.4 * attention_score + 0.5 * task_relevance + 0.1 * (1 - state.uncertainty)
    if action == "TYPE":
        base += 0.1
    urgency = 0.2 * goal_directedness - 0.1 * (1 - patience)
    return _clip(base + urgency - repeat_penalty)


def _action_confidence(
    traits: dict[str, float], state: ParticipantState, task_relevance: float
) -> float:
    digital_confidence = traits.get("digital_confidence", 0.5)
    return _clip(0.3 + 0.4 * digital_confidence + 0.3 * task_relevance - 0.2 * state.uncertainty)


def _scroll_utility(context: SimulationContext) -> float:
    exploration = context.participant.traits.get("exploration", 0.5)
    max_attention = (
        max((c.attention_score for c in context.attention.candidates), default=0.0)
        if context.attention
        else 0.0
    )
    return _clip(0.5 * exploration + 0.3 * (1 - max_attention) + 0.2 * context.state.uncertainty)


def _back_utility(context: SimulationContext) -> float:
    patience = context.participant.traits.get("patience", 0.5)
    dead_end_pressure = min(1.0, context.state.dead_end_count / 3)
    return _clip(
        0.2 + 0.4 * context.state.uncertainty + 0.2 * (1 - patience) + 0.1 * dead_end_pressure
    )


class HeuristicParticipantModel:
    """LLD §9 (Attention Engine) + §11 (Interaction Policy), computed directly
    from the screen/task/persona/state data — see module docstring."""

    async def select_attention(self, context: SimulationContext) -> AttentionDecision:
        weights = _attention_weights(context.participant.traits)
        candidates = []
        for element in context.screen.elements:
            visual = _visual_saliency(element, context.screen)
            task_relevance = _task_relevance(element, context.task)
            persona_relevance = _persona_relevance(element, context.participant.traits)
            state_relevance = _state_relevance(element, context.state)
            score = (
                weights["visual"] * visual
                + weights["task"] * task_relevance
                + weights["persona"] * persona_relevance
                + weights["state"] * state_relevance
            )
            candidates.append(
                AttentionCandidate(
                    element_id=str(element.id),
                    visual_saliency=visual,
                    task_relevance=task_relevance,
                    persona_relevance=persona_relevance,
                    state_relevance=state_relevance,
                    attention_score=_clip(score),
                )
            )
        return AttentionDecision(candidates=candidates)

    async def select_action(self, context: SimulationContext) -> ActionDecision:
        attention_by_element = {
            c.element_id: c for c in (context.attention.candidates if context.attention else [])
        }
        candidates = []
        for element in context.screen.elements:
            if not element.interactable:
                continue
            action = _default_action_for(element)
            attended = attention_by_element.get(str(element.id))
            attention_score = attended.attention_score if attended else 0.3
            task_relevance = (
                attended.task_relevance if attended else _task_relevance(element, context.task)
            )
            repeat_penalty = _repeat_penalty(context.state, action, element.id)
            utility = _action_utility(
                action,
                attention_score,
                task_relevance,
                context.participant.traits,
                context.state,
                repeat_penalty,
            )
            confidence = _action_confidence(
                context.participant.traits, context.state, task_relevance
            )
            candidates.append(
                ActionCandidate(
                    action=action, target=str(element.id), utility=utility, confidence=confidence
                )
            )
        candidates.append(
            ActionCandidate(
                action="SCROLL", target=None, utility=_scroll_utility(context), confidence=0.4
            )
        )
        if context.state.action_history and context.state.backtrack_count < 3:
            candidates.append(
                ActionCandidate(
                    action="BACK", target=None, utility=_back_utility(context), confidence=0.4
                )
            )
        return ActionDecision(candidates=candidates)


class RandomParticipantModel:
    """Baseline: ignores every signal, equal score for every candidate — any
    resulting diversity comes purely from the graph's seeded sampling."""

    async def select_attention(self, context: SimulationContext) -> AttentionDecision:
        return AttentionDecision(
            candidates=[
                AttentionCandidate(
                    element_id=str(element.id),
                    visual_saliency=0.0,
                    task_relevance=0.0,
                    persona_relevance=0.0,
                    state_relevance=0.0,
                    attention_score=0.5,
                )
                for element in context.screen.elements
            ]
        )

    async def select_action(self, context: SimulationContext) -> ActionDecision:
        candidates = [
            ActionCandidate(
                action=_default_action_for(element),
                target=str(element.id),
                utility=0.5,
                confidence=0.5,
            )
            for element in context.screen.elements
            if element.interactable
        ]
        candidates.append(
            ActionCandidate(action="SCROLL", target=None, utility=0.5, confidence=0.5)
        )
        return ActionDecision(candidates=candidates)


class SaliencyOnlyParticipantModel:
    """Baseline: visual saliency only, no task/persona/state signal."""

    async def select_attention(self, context: SimulationContext) -> AttentionDecision:
        candidates = []
        for element in context.screen.elements:
            visual = _visual_saliency(element, context.screen)
            candidates.append(
                AttentionCandidate(
                    element_id=str(element.id),
                    visual_saliency=visual,
                    task_relevance=0.0,
                    persona_relevance=0.0,
                    state_relevance=0.0,
                    attention_score=visual,
                )
            )
        return AttentionDecision(candidates=candidates)

    async def select_action(self, context: SimulationContext) -> ActionDecision:
        attention_by_element = {
            c.element_id: c.attention_score
            for c in (context.attention.candidates if context.attention else [])
        }
        candidates = [
            ActionCandidate(
                action=_default_action_for(element),
                target=str(element.id),
                utility=attention_by_element.get(str(element.id), 0.3),
                confidence=0.5,
            )
            for element in context.screen.elements
            if element.interactable
        ]
        candidates.append(
            ActionCandidate(action="SCROLL", target=None, utility=0.3, confidence=0.5)
        )
        return ActionDecision(candidates=candidates)


class TaskOnlyParticipantModel:
    """Baseline: task-instruction relevance only, no visual/persona/state signal."""

    async def select_attention(self, context: SimulationContext) -> AttentionDecision:
        candidates = []
        for element in context.screen.elements:
            task_relevance = _task_relevance(element, context.task)
            candidates.append(
                AttentionCandidate(
                    element_id=str(element.id),
                    visual_saliency=0.0,
                    task_relevance=task_relevance,
                    persona_relevance=0.0,
                    state_relevance=0.0,
                    attention_score=task_relevance,
                )
            )
        return AttentionDecision(candidates=candidates)

    async def select_action(self, context: SimulationContext) -> ActionDecision:
        candidates = [
            ActionCandidate(
                action=_default_action_for(element),
                target=str(element.id),
                utility=_task_relevance(element, context.task),
                confidence=0.5,
            )
            for element in context.screen.elements
            if element.interactable
        ]
        candidates.append(
            ActionCandidate(action="SCROLL", target=None, utility=0.2, confidence=0.5)
        )
        return ActionDecision(candidates=candidates)


PARTICIPANT_MODELS: dict[str, type[ParticipantModel]] = {
    "heuristic": HeuristicParticipantModel,
    "random": RandomParticipantModel,
    "saliency_only": SaliencyOnlyParticipantModel,
    "task_only": TaskOnlyParticipantModel,
}


def get_participant_model(name: str | None) -> ParticipantModel:
    """`name` comes from `simulation_runs.config["participant_model"]` — lets a
    baseline-comparison run (planning/07 "Baseline participant models") reuse
    the exact same job/graph, just swapping this one construction site."""
    model_cls = PARTICIPANT_MODELS.get(name or "heuristic", HeuristicParticipantModel)
    return model_cls()
