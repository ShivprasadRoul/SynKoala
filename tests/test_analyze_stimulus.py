import uuid

from app.agents.providers.vision_provider import InferredTransition
from app.db.models import ScreenModel, UIElementModel
from app.workers.jobs.analyze_stimulus import _resolve_transitions, _screen_summary

HOME_ID = uuid.uuid4()
CONFIRM_ID = uuid.uuid4()
CHECKOUT_ID = uuid.uuid4()
CTA_ID = uuid.uuid4()


def _home_screen() -> ScreenModel:
    return ScreenModel(
        id=HOME_ID,
        stimulus_id=uuid.uuid4(),
        screen_key="home",
        width=390,
        height=844,
        elements=[
            UIElementModel(
                id=CTA_ID,
                screen_id=HOME_ID,
                element_key="cta",
                type="button",
                text="Add to cart",
                bbox=[20, 720, 370, 776],
                properties={"semantic_role": "primary_action", "interactable": True},
            )
        ],
    )


def _confirm_screen() -> ScreenModel:
    return ScreenModel(
        id=CONFIRM_ID,
        stimulus_id=uuid.uuid4(),
        screen_key="confirm",
        width=390,
        height=844,
        elements=[],
    )


def _checkout_screen() -> ScreenModel:
    return ScreenModel(
        id=CHECKOUT_ID,
        stimulus_id=uuid.uuid4(),
        screen_key="checkout",
        width=390,
        height=844,
        elements=[],
    )


def test_screen_summary_reads_semantic_role_and_interactable_from_properties():
    summary = _screen_summary(_home_screen())

    assert summary.screen_key == "home"
    assert summary.elements[0].element_key == "cta"
    assert summary.elements[0].semantic_role == "primary_action"
    assert summary.elements[0].interactable is True


def test_screen_summary_defaults_when_properties_missing():
    screen = _home_screen()
    screen.elements[0].properties = None

    summary = _screen_summary(screen)

    assert summary.elements[0].semantic_role == ""
    assert summary.elements[0].interactable is False


def test_resolve_transitions_maps_valid_edge_to_real_ids():
    screens = [_home_screen(), _confirm_screen()]
    edge = InferredTransition(
        from_screen_key="home", element_key="cta", action="CLICK", to_screen_key="confirm"
    )

    resolved = _resolve_transitions(screens, [edge])

    assert resolved == [
        {
            "from_screen_id": HOME_ID,
            "trigger_element_id": CTA_ID,
            "action": "CLICK",
            "to_screen_id": CONFIRM_ID,
        }
    ]


def test_resolve_transitions_drops_hallucinated_references():
    """The model is asked never to invent a screen/element key it wasn't given,
    but the caller can't just trust that (never let a model self-report what it
    can't back up) — anything that doesn't resolve to a real row is dropped."""
    screens = [_home_screen(), _confirm_screen()]
    real_edge = InferredTransition(
        from_screen_key="home", element_key="cta", action="CLICK", to_screen_key="confirm"
    )
    fake_screen_edge = InferredTransition(
        from_screen_key="home", element_key="cta", action="CLICK", to_screen_key="checkout"
    )
    fake_element_edge = InferredTransition(
        from_screen_key="home",
        element_key="does_not_exist",
        action="CLICK",
        to_screen_key="confirm",
    )

    resolved = _resolve_transitions(screens, [real_edge, fake_screen_edge, fake_element_edge])

    assert len(resolved) == 1
    assert resolved[0]["trigger_element_id"] == CTA_ID


def test_resolve_transitions_keeps_only_the_first_destination_for_a_conflicting_trigger():
    """Regression test: one button in one screen state cannot navigate to two
    different screens. A model that reports the same (from_screen, element)
    with two different destinations (observed in practice — see chat) must
    resolve to exactly one edge, not both; without this, `execute_action`'s
    `next(...)` over `transitions_from` would pick whichever conflicting edge
    Postgres happened to return first, non-reproducible for the same
    participant/seed (PRD §7)."""
    screens = [_home_screen(), _confirm_screen(), _checkout_screen()]
    first_edge = InferredTransition(
        from_screen_key="home", element_key="cta", action="CLICK", to_screen_key="confirm"
    )
    conflicting_edge = InferredTransition(
        from_screen_key="home", element_key="cta", action="CLICK", to_screen_key="checkout"
    )

    resolved = _resolve_transitions(screens, [first_edge, conflicting_edge])

    assert len(resolved) == 1
    assert resolved[0]["to_screen_id"] == CONFIRM_ID


def test_resolve_transitions_collapses_an_exact_duplicate_edge():
    screens = [_home_screen(), _confirm_screen()]
    edge = InferredTransition(
        from_screen_key="home", element_key="cta", action="CLICK", to_screen_key="confirm"
    )

    resolved = _resolve_transitions(screens, [edge, edge])

    assert len(resolved) == 1
