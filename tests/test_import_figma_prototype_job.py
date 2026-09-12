import uuid

from app.services.figma_import_service import ParsedDocument, ParsedElement, ParsedScreen
from app.workers.jobs.import_figma_prototype import _resolve_transitions


def _cta_screen(transition_to_node_id: str | None) -> ParsedScreen:
    return ParsedScreen(
        node_id="1:1",
        name="Home",
        width=390,
        height=844,
        elements=[
            ParsedElement(
                node_id="1:2",
                name="CTA",
                type="INSTANCE",
                text=None,
                bbox=[0, 0, 10, 10],
                interactable=True,
                semantic_role="primary_action",
                transition_to_node_id=transition_to_node_id,
            )
        ],
    )


def test_resolve_transitions_maps_figma_node_ids_to_the_persisted_row_ids():
    home_id, confirm_id, cta_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    parsed = ParsedDocument(
        screens=[
            _cta_screen(transition_to_node_id="2:1"),
            ParsedScreen(node_id="2:1", name="Confirm", width=390, height=844),
        ]
    )

    transitions = _resolve_transitions(
        parsed,
        screens_by_node_id={"1:1": home_id, "2:1": confirm_id},
        elements_by_node_id={"1:2": cta_id},
    )

    assert transitions == [
        {
            "from_screen_id": home_id,
            "trigger_element_id": cta_id,
            "action": "CLICK",
            "to_screen_id": confirm_id,
        }
    ]


def test_resolve_transitions_drops_a_transition_to_a_screen_that_was_never_persisted():
    """Figma's transitionNodeID is real data, not a model guess, but it can
    still point at a node this import didn't treat as a screen (e.g. a
    component variant Figma never exposed as a top-level frame) — same
    "never trust an external reference blindly" rule as
    app/workers/jobs/analyze_stimulus.py's _resolve_transitions."""
    home_id, cta_id = uuid.uuid4(), uuid.uuid4()
    parsed = ParsedDocument(screens=[_cta_screen(transition_to_node_id="does-not-exist")])

    transitions = _resolve_transitions(
        parsed,
        screens_by_node_id={"1:1": home_id},
        elements_by_node_id={"1:2": cta_id},
    )

    assert transitions == []


def test_resolve_transitions_ignores_elements_with_no_transition():
    parsed = ParsedDocument(screens=[_cta_screen(transition_to_node_id=None)])

    transitions = _resolve_transitions(
        parsed,
        screens_by_node_id={"1:1": uuid.uuid4()},
        elements_by_node_id={"1:2": uuid.uuid4()},
    )

    assert transitions == []
