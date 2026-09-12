"""LLD §28 `VisionProvider` protocol, plus the real implementation
(planning/05-stimulus-engine.md).

Unlike `ParticipantModel` (`app/agents/providers/participant_model.py`), there is no
honest heuristic substitute here: extracting real UI structure from a screenshot's
pixels genuinely requires a vision-capable model call, not a formula over data we
don't have yet. So `PydanticAIVisionProvider` is the only implementation — it can't
run without a configured model provider API key (`settings.vision_model`, read by
Pydantic AI itself), and that's the correct failure mode: `analyze_stimulus` should
fail clearly rather than fabricate elements that were never really seen (the same
"never let a model self-report what it can't back up" principle that governs
heatmaps/insights elsewhere in this codebase — see
`.claude/skills/backend-feature/SKILL.md` §4 — applies just as much to inventing the
UI structure itself).

`infer_transitions` is an extension beyond the LLD §28 Protocol's literal two
methods (`analyze_screen` only) — the screen-graph inference pass planning/05's
prose describes ("asking the same model 'which element on screen A, if triggered,
leads to screen B'") needed a concrete shape, which didn't exist anywhere yet. Noted
in `05-stimulus-engine.md` as a planning decision made here.
"""

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent

from app.core.settings import settings


class ScreenElement(BaseModel):
    id: str
    type: str
    text: str | None
    bbox: tuple[int, int, int, int]
    semantic_role: str
    interactable: bool


class ScreenAnalysis(BaseModel):
    elements: list[ScreenElement]


class ScreenElementSummary(BaseModel):
    element_key: str
    type: str
    text: str | None
    semantic_role: str
    interactable: bool


class ScreenSummary(BaseModel):
    screen_key: str
    elements: list[ScreenElementSummary]


class InferredTransition(BaseModel):
    from_screen_key: str
    element_key: str
    action: Literal["CLICK", "TAP", "OPEN", "SELECT"]
    to_screen_key: str


class ScreenGraphInference(BaseModel):
    transitions: list[InferredTransition]


@runtime_checkable
class VisionProvider(Protocol):
    async def analyze_screen(self, image: bytes, content_type: str) -> ScreenAnalysis: ...

    async def infer_transitions(self, screens: list[ScreenSummary]) -> ScreenGraphInference: ...


_ANALYZE_SYSTEM_PROMPT = (
    "You are analyzing a single UI screenshot for a UX research tool. Identify every "
    "visible UI element. For each one, give: a stable short id, lowercase snake_case, "
    "unique on this screen (e.g. 'search_input', 'add_to_cart_button'); its type "
    "(button, input, link, image, text, select, checkbox, radio, ...); its visible text "
    "if any; its pixel bounding box as [x1, y1, x2, y2]; a semantic_role describing its "
    "purpose (e.g. primary_action, search, navigation, help, confirmation, info); and "
    "whether a user could interact with it (interactable). Only report elements you can "
    "actually see — do not invent elements."
)

_TRANSITIONS_SYSTEM_PROMPT = (
    "You are inferring navigation between screens of a UI prototype from their already-"
    "analyzed elements. You will be given a list of screens, each with its elements. For "
    "each interactable element, decide whether triggering it plausibly navigates to one "
    "of the OTHER listed screens, and if so, to which one. Only report a transition when "
    "reasonably confident; every from_screen_key, element_key, and to_screen_key you "
    "report must exactly match one given to you — never invent one."
)


class PydanticAIVisionProvider:
    def __init__(self, model: str | None = None) -> None:
        self._model = model or settings.vision_model

    async def analyze_screen(self, image: bytes, content_type: str) -> ScreenAnalysis:
        agent = Agent(self._model, output_type=ScreenAnalysis, system_prompt=_ANALYZE_SYSTEM_PROMPT)
        result = await agent.run(
            ["Analyze this screen.", BinaryContent(data=image, media_type=content_type)]
        )
        return result.output

    async def infer_transitions(self, screens: list[ScreenSummary]) -> ScreenGraphInference:
        if len(screens) < 2:
            return ScreenGraphInference(transitions=[])
        agent = Agent(
            self._model, output_type=ScreenGraphInference, system_prompt=_TRANSITIONS_SYSTEM_PROMPT
        )
        payload = [screen.model_dump() for screen in screens]
        result = await agent.run([f"Screens: {payload}"])
        return result.output
