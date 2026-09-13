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

from typing import Annotated, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent

from app.core.settings import settings

# Pydantic's JSON schema for a fixed-length tuple (`tuple[int, int, int, int]`) uses
# `prefixItems` with no `items` key — several providers' strict structured-output
# validators (e.g. OpenAI's function-calling schema check) reject that shape. A
# length-constrained plain array avoids it while still round-tripping as [x1, y1, x2, y2].
BBox = Annotated[list[int], Field(min_length=4, max_length=4)]


class ScreenElement(BaseModel):
    id: str
    type: str
    text: str | None
    bbox: BBox
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


class ScreenRole(BaseModel):
    """What a screen *is* within the flow, as opposed to what it contains.

    `duplicate_of` is the load-bearing field: a researcher uploading a flow
    routinely captures the same UI state more than once (unfilled vs. filled,
    keyboard open vs. closed). Those arrive as separate screens, and
    `infer_transitions` then scatters the flow's incoming edges onto one twin
    and its outgoing edges onto the other — severing the graph so most of the
    prototype is unreachable. Naming the twin here lets the caller collapse
    them back onto one node.
    """

    screen_key: str
    summary: str
    role: Literal["entry", "step", "success", "error", "other"]
    duplicate_of: str | None


class ScreenRoleInference(BaseModel):
    screens: list[ScreenRole]


@runtime_checkable
class VisionProvider(Protocol):
    async def analyze_screen(self, image: bytes, content_type: str) -> ScreenAnalysis: ...

    async def infer_transitions(self, screens: list[ScreenSummary]) -> ScreenGraphInference: ...

    async def classify_screens(self, screens: list[ScreenSummary]) -> ScreenRoleInference: ...


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
    "of the OTHER listed screens, and if so, to which one.\n\n"
    "Many screens share elements with the same generic name and role across the whole "
    "prototype (e.g. a 'back_button' or 'continue_button' appears on several different "
    "screens) — these are DIFFERENT elements that just happen to be named alike; do not "
    "let that similarity make you report the same kind of transition for all of them. "
    "Judge each element only by what its OWN screen's content implies is the next or "
    "previous step, not by its label alone.\n\n"
    "A single element can trigger at most ONE transition — it is one button in one "
    "screen, it cannot navigate to two different screens. If a screen's step/progress "
    "indicator gives an explicit order (e.g. '1 / 3', '2 / 3', 'Step 2 of 4'), a forward "
    "action on it should target the next step in that order, and a back/navigation "
    "action should target the previous one — never guess a destination that contradicts "
    "an explicit order like this.\n\n"
    "Report an element only when you are reasonably confident of exactly one destination; "
    "if multiple destinations seem equally plausible, or you are unsure, omit that element "
    "entirely rather than reporting your best guess. Every from_screen_key, element_key, "
    "and to_screen_key you report must exactly match one given to you — never invent one."
)


_CLASSIFY_SYSTEM_PROMPT = (
    "You are identifying the shape of a UI prototype flow from its already-analyzed "
    "screens. You will be given a list of screens, each with its elements, in the order "
    "the researcher uploaded them. For EVERY screen given to you, report:\n\n"
    "- summary: one short sentence describing what this screen is and what the user does "
    "on it, based only on its actual elements and their text.\n"
    "- role: 'entry' for the screen a user starts on (a launch, landing, splash or sign-in "
    "chooser screen — exactly ONE screen may be 'entry'); 'success' for the screen that "
    "means the user's journey finished successfully (a confirmation, 'account created', "
    "'order placed', 'welcome' screen — at most ONE screen may be 'success'); 'error' for "
    "a failure/validation state; 'step' for an ordinary intermediate step; 'other' when "
    "none of these fit.\n"
    "- duplicate_of: when this screen shows the SAME underlying UI state as an earlier "
    "screen in the list and differs only in transient presentation — empty vs. filled-in "
    "fields, keyboard shown or hidden, a validation hint, a hover/focus highlight — set "
    "this to that earlier screen's screen_key. Otherwise null. Two screens are NOT "
    "duplicates just because they look similar or share a layout: a password step and a "
    "verify-email step are different states even if both are one input and one button. "
    "Only say duplicate_of when a user would say they are on the same screen.\n\n"
    "Judge 'entry' and 'success' by what the screens actually say, not by their position "
    "in the list — a flow's last uploaded screen is often, but not always, its success "
    "screen. Every screen_key you report, including in duplicate_of, must exactly match "
    "one given to you — never invent one, and never point duplicate_of at itself."
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

    async def classify_screens(self, screens: list[ScreenSummary]) -> ScreenRoleInference:
        if not screens:
            return ScreenRoleInference(screens=[])
        agent = Agent(
            self._model, output_type=ScreenRoleInference, system_prompt=_CLASSIFY_SYSTEM_PROMPT
        )
        payload = [screen.model_dump() for screen in screens]
        result = await agent.run([f"Screens, in upload order: {payload}"])
        return result.output
