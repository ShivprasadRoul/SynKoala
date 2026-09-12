import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import LifecycleError
from app.core.settings import settings
from app.core.storage import ensure_bucket, upload_object
from app.services.figma_import_service import FigmaImportService, ParsedDocument, ParsedScreen
from app.services.figma_oauth_service import FigmaOAuthService
from app.services.stimulus_service import StimulusService


async def _download(url: str) -> tuple[bytes, str]:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content, response.headers.get("content-type", "image/png")


def _elements_for_persistence(screen: ParsedScreen) -> list[dict]:
    return [
        {
            "element_key": element.node_id,
            "type": element.type,
            "text": element.text,
            "bbox": element.bbox,
            "semantic_role": element.semantic_role,
            "interactable": element.interactable,
        }
        for element in screen.elements
    ]


def _resolve_transitions(
    parsed: ParsedDocument,
    screens_by_node_id: dict[str, uuid.UUID],
    elements_by_node_id: dict[str, uuid.UUID],
) -> list[dict]:
    """Maps Figma's own node ids back onto the just-persisted row ids, same
    "never trust an external reference blindly" rule as
    `app/workers/jobs/analyze_stimulus.py`'s `_resolve_transitions` — except
    here the source is Figma's real `transitionNodeID` data, not a model
    guess, so the only thing to guard against is a transition pointing at a
    node this import didn't end up treating as a screen (e.g. a component
    variant Figma didn't expose as a top-level frame)."""
    transitions = []
    for screen in parsed.screens:
        from_screen_id = screens_by_node_id.get(screen.node_id)
        if from_screen_id is None:
            continue
        for element in screen.elements:
            if not element.transition_to_node_id:
                continue
            to_screen_id = screens_by_node_id.get(element.transition_to_node_id)
            trigger_element_id = elements_by_node_id.get(element.node_id)
            if to_screen_id is None or trigger_element_id is None:
                continue
            transitions.append(
                {
                    "from_screen_id": from_screen_id,
                    "trigger_element_id": trigger_element_id,
                    "action": "CLICK",
                    "to_screen_id": to_screen_id,
                }
            )
    return transitions


async def handle_import_figma_prototype(session: AsyncSession, payload: dict) -> None:
    """Stimulus Engine's Figma import path (planning/05-stimulus-engine.md):
    fetches a Figma prototype's document tree via the connected account's
    OAuth token, persists every frame as a real `screens`/`ui_elements` row
    (ground truth from Figma's own node data — no vision-model call needed
    for a Figma-sourced stimulus), and rebuilds the study's
    `screen_transitions` from Figma's own `transitionNodeID` links. Re-uploads
    every screen's rendered image into this app's own storage bucket rather
    than depending on Figma's URLs, which expire after 30 days."""
    stimuli = StimulusService(session)
    figma_oauth = FigmaOAuthService(session)
    figma = FigmaImportService()

    stimulus_id = uuid.UUID(payload["stimulus_id"])
    user_id = uuid.UUID(payload["user_id"])

    stimulus = await stimuli.get_with_screens(stimulus_id)
    if not stimulus.source_url:
        raise LifecycleError(f"Stimulus {stimulus_id} has no Figma prototype URL to import")

    access_token = await figma_oauth.get_valid_access_token(user_id)
    file_key = FigmaImportService.extract_file_key(stimulus.source_url)

    document = await figma.fetch_document(access_token, file_key)
    parsed = figma.parse_document(document)
    if not parsed.screens:
        raise LifecycleError(f"No frames found in Figma file {file_key}")

    image_urls = await figma.fetch_image_urls(
        access_token, file_key, [screen.node_id for screen in parsed.screens]
    )
    await ensure_bucket(settings.supabase_storage_bucket)

    screens_by_node_id: dict[str, uuid.UUID] = {}
    elements_by_node_id: dict[str, uuid.UUID] = {}

    for screen in parsed.screens:
        stored_image_url = None
        figma_image_url = image_urls.get(screen.node_id)
        if figma_image_url:
            image_bytes, content_type = await _download(figma_image_url)
            stored_image_url = await upload_object(
                settings.supabase_storage_bucket,
                f"{stimulus.id}/{screen.node_id}",
                image_bytes,
                content_type,
            )
        screen_model, element_models = await stimuli.save_figma_screen(
            stimulus_id=stimulus.id,
            screen_key=screen.node_id,
            name=screen.name,
            width=screen.width,
            height=screen.height,
            image_url=stored_image_url,
            elements=_elements_for_persistence(screen),
        )
        screens_by_node_id[screen.node_id] = screen_model.id
        for element, element_model in zip(screen.elements, element_models, strict=True):
            elements_by_node_id[element.node_id] = element_model.id

    transitions = _resolve_transitions(parsed, screens_by_node_id, elements_by_node_id)
    await stimuli.replace_transitions_for_study(stimulus.study_id, transitions)
    await stimuli.save_import_metadata(
        stimulus,
        {
            "file_key": file_key,
            "screens": [
                {"node_id": s.node_id, "name": s.name, "width": s.width, "height": s.height}
                for s in parsed.screens
            ],
            "transitions": [
                {
                    "from_screen_node_id": screen.node_id,
                    "trigger_node_id": element.node_id,
                    "to_screen_node_id": element.transition_to_node_id,
                }
                for screen in parsed.screens
                for element in screen.elements
                if element.transition_to_node_id
            ],
        },
    )
