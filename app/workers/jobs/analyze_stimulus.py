import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.providers.vision_provider import (
    InferredTransition,
    PydanticAIVisionProvider,
    ScreenAnalysis,
    ScreenElementSummary,
    ScreenGraphInference,
    ScreenSummary,
)
from app.core.errors import LifecycleError
from app.core.storage import download_object
from app.db.models import ScreenModel
from app.services.stimulus_service import StimulusService


def _elements_for_persistence(analysis: ScreenAnalysis) -> list[dict]:
    return [
        {
            "element_key": element.id,
            "type": element.type,
            "text": element.text,
            "bbox": list(element.bbox),
            "semantic_role": element.semantic_role,
            "interactable": element.interactable,
        }
        for element in analysis.elements
    ]


def _screen_summary(screen: ScreenModel) -> ScreenSummary:
    return ScreenSummary(
        screen_key=screen.screen_key,
        elements=[
            ScreenElementSummary(
                element_key=element.element_key,
                type=element.type,
                text=element.text,
                semantic_role=(element.properties or {}).get("semantic_role", ""),
                interactable=bool((element.properties or {}).get("interactable", False)),
            )
            for element in screen.elements
        ],
    )


def _resolve_transitions(
    screens: list[ScreenModel], inferred: list[InferredTransition]
) -> list[dict]:
    """Maps the model's `(screen_key, element_key)` references back onto real
    rows, dropping anything that doesn't resolve — the model is asked never to
    invent one (see `vision_provider.py`'s system prompt), but "never let a
    model self-report what it can't back up" (`.claude/skills/backend-feature/
    SKILL.md` §4) means the caller can't just trust that."""
    screens_by_key = {screen.screen_key: screen for screen in screens}
    elements_by_screen_and_key = {
        (screen.screen_key, element.element_key): element
        for screen in screens
        for element in screen.elements
    }
    transitions = []
    for edge in inferred:
        from_screen = screens_by_key.get(edge.from_screen_key)
        to_screen = screens_by_key.get(edge.to_screen_key)
        trigger_element = elements_by_screen_and_key.get((edge.from_screen_key, edge.element_key))
        if from_screen is None or to_screen is None or trigger_element is None:
            continue
        transitions.append(
            {
                "from_screen_id": from_screen.id,
                "trigger_element_id": trigger_element.id,
                "action": edge.action,
                "to_screen_id": to_screen.id,
            }
        )
    return transitions


async def handle_analyze_stimulus(session: AsyncSession, payload: dict) -> None:
    """VisionProvider (planning/05-stimulus-engine.md): analyzes every not-yet-
    analyzed screen belonging to this stimulus, then re-infers the screen graph
    (LLD §7) across every analyzed screen in the whole study — a multi-screen
    prototype flow is one screen per `stimuli` row today
    (`StimulusService.create_with_asset`), so a screen can only ever connect to a
    *sibling* stimulus's screen, never one of its own."""
    stimuli = StimulusService(session)
    stimulus_id = uuid.UUID(payload["stimulus_id"])
    stimulus = await stimuli.get_with_screens(stimulus_id)
    provider = PydanticAIVisionProvider()

    for screen in stimulus.screens:
        if screen.elements:
            continue  # already analyzed (e.g. a retried job after a later screen failed)
        if not screen.image_url:
            raise LifecycleError(f"Screen {screen.id} has no uploaded image to analyze")
        image_bytes, content_type = await download_object(screen.image_url)
        analysis = await provider.analyze_screen(image_bytes, content_type)
        await stimuli.save_screen_analysis(
            screen,
            elements=_elements_for_persistence(analysis),
            raw_analysis=analysis.model_dump(),
        )

    study_screens = [
        screen
        for screen in await stimuli.list_screens_for_study(stimulus.study_id)
        if screen.analysis is not None
    ]
    if len(study_screens) < 2:
        return  # nothing to connect yet

    inference: ScreenGraphInference = await provider.infer_transitions(
        [_screen_summary(screen) for screen in study_screens]
    )
    transitions = _resolve_transitions(study_screens, inference.transitions)
    await stimuli.replace_transitions_for_study(stimulus.study_id, transitions)
