import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.providers.vision_provider import (
    InferredTransition,
    PydanticAIVisionProvider,
    ScreenAnalysis,
    ScreenElementSummary,
    ScreenGraphInference,
    ScreenRole,
    ScreenRoleInference,
    ScreenSummary,
)
from app.core.errors import LifecycleError
from app.core.storage import download_object
from app.db.models import ScreenModel
from app.services.stimulus_service import StimulusService

logger = logging.getLogger(__name__)


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


def _resolve_screen_roles(
    screens: list[ScreenModel], inferred: list[ScreenRole]
) -> dict[str, dict]:
    """Validates `classify_screens` output against the real screens, applying the
    same "never trust what the model can't back up" rule `_resolve_transitions`
    uses: a `screen_key` or `duplicate_of` naming a screen that doesn't exist is
    dropped rather than persisted.

    `duplicate_of` may only point *backwards* in upload order. That's what makes
    the collapse well-defined — it can't cycle, every chain terminates at an
    earliest screen, and which twin survives doesn't depend on which order the
    model happened to list them in. `entry`/`success` are each unique by
    construction: if the model marks several, the earliest-uploaded wins for
    `entry` and the latest for `success`, since that is where each actually sits
    in a flow."""
    order = {screen.screen_key: index for index, screen in enumerate(screens)}
    roles: dict[str, dict] = {}
    for reported in inferred:
        if reported.screen_key not in order:
            logger.warning("classify_screens: unknown screen_key %s", reported.screen_key)
            continue
        duplicate_of = reported.duplicate_of
        if duplicate_of is not None and (
            duplicate_of not in order or order[duplicate_of] >= order[reported.screen_key]
        ):
            logger.warning(
                "classify_screens: dropping duplicate_of %s -> %s (unknown or not earlier)",
                reported.screen_key,
                duplicate_of,
            )
            duplicate_of = None
        roles[reported.screen_key] = {
            "summary": reported.summary,
            "role": reported.role,
            "duplicate_of": duplicate_of,
        }

    for role_name, keep in (("entry", min), ("success", max)):
        claimants = [key for key, role in roles.items() if role["role"] == role_name]
        if len(claimants) > 1:
            winner = keep(claimants, key=lambda key: order[key])
            for key in claimants:
                if key != winner:
                    roles[key]["role"] = "step"
    return roles


def _canonical_screen_keys(roles: dict[str, dict]) -> dict[str, str]:
    """`screen_key -> the key it collapses onto`, following `duplicate_of`
    chains to their root. Terminates because `_resolve_screen_roles` only
    admits backwards-pointing links."""
    canonical: dict[str, str] = {}
    for key in roles:
        seen = {key}
        current = key
        while (parent := roles.get(current, {}).get("duplicate_of")) and parent not in seen:
            seen.add(parent)
            current = parent
        canonical[key] = current
    return canonical


def _resolve_transitions(
    screens: list[ScreenModel],
    inferred: list[InferredTransition],
    canonical: dict[str, str] | None = None,
) -> list[dict]:
    """Maps the model's `(screen_key, element_key)` references back onto real
    rows, dropping anything that doesn't resolve — the model is asked never to
    invent one (see `vision_provider.py`'s system prompt), but "never let a
    model self-report what it can't back up" (`.claude/skills/backend-feature/
    SKILL.md` §4) means the caller can't just trust that.

    Also enforces that a single (screen, trigger element) can resolve to at
    most one destination screen — one button in one app state cannot navigate
    two different places, so a second, conflicting destination for a trigger
    already seen is dropped (first inferred edge wins) rather than persisted.
    Without this, `execute_action`'s `next(... for t in transitions_from(...))`
    would pick whichever of several contradictory edges Postgres happened to
    return first — undefined, and not reproducible run-to-run for the same
    participant/seed (PRD §7).

    `canonical` collapses duplicate screens (see `_resolve_screen_roles`) as
    edges are resolved: both endpoints are remapped onto the surviving twin, so
    an edge arriving at one twin and an edge leaving the other end up on the
    same node instead of severing the flow between them. The trigger is
    re-looked-up by `element_key` on the surviving screen, because
    `execute_action` matches transitions against elements of the screen the
    participant is actually standing on — an edge whose trigger has no
    counterpart there could never fire, so it's dropped rather than persisted.
    An edge that collapses onto a self-loop is dropped too: it described
    movement between two renderings of one screen, which is not navigation."""
    canonical = canonical or {}
    screens_by_key = {screen.screen_key: screen for screen in screens}
    elements_by_screen_and_key = {
        (screen.screen_key, element.element_key): element
        for screen in screens
        for element in screen.elements
    }
    transitions: list[dict] = []
    seen_triggers: dict[tuple[uuid.UUID, uuid.UUID], uuid.UUID] = {}
    for edge in inferred:
        from_key = canonical.get(edge.from_screen_key, edge.from_screen_key)
        to_key = canonical.get(edge.to_screen_key, edge.to_screen_key)
        from_screen = screens_by_key.get(from_key)
        to_screen = screens_by_key.get(to_key)
        trigger_element = elements_by_screen_and_key.get((from_key, edge.element_key))
        if from_screen is None or to_screen is None or trigger_element is None:
            continue
        if from_screen.id == to_screen.id:
            continue
        trigger_key = (from_screen.id, trigger_element.id)
        existing_destination = seen_triggers.get(trigger_key)
        if existing_destination is not None:
            if existing_destination != to_screen.id:
                logger.warning(
                    "infer_transitions: dropping conflicting destination for "
                    "screen=%s element=%s — already resolved to %s, model also "
                    "reported %s",
                    edge.from_screen_key,
                    edge.element_key,
                    existing_destination,
                    to_screen.id,
                )
            continue
        seen_triggers[trigger_key] = to_screen.id
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

    summaries = [_screen_summary(screen) for screen in study_screens]

    # Classify before inferring the graph: which screens are really one screen
    # decides which nodes the transitions may land on, and the entry/success
    # roles are what the task builder prefills a flow's start and finish line
    # from (planning/05-stimulus-engine.md).
    classification: ScreenRoleInference = await provider.classify_screens(summaries)
    roles = _resolve_screen_roles(study_screens, classification.screens)
    await stimuli.save_screen_roles(study_screens, roles)
    canonical = _canonical_screen_keys(roles)

    # Infer the graph over the surviving screens only. Shown every twin, the
    # model spends its edges describing the step between two renderings of one
    # screen ("unfilled -> filled") instead of the step to the next real screen,
    # which is how a flow ends up severed. Collapsing first means each node it
    # sees is a distinct state a user can actually be in.
    surviving = [
        screen for screen in study_screens if canonical.get(screen.screen_key) == screen.screen_key
    ]
    inference: ScreenGraphInference = await provider.infer_transitions(
        [_screen_summary(screen) for screen in surviving]
    )
    transitions = _resolve_transitions(study_screens, inference.transitions, canonical)
    await stimuli.replace_transitions_for_study(stimulus.study_id, transitions)
