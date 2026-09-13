import uuid

from app.agents.providers.vision_provider import InferredTransition, ScreenRole
from app.db.models import ScreenModel, UIElementModel
from app.workers.jobs.analyze_stimulus import (
    _canonical_screen_keys,
    _resolve_screen_roles,
    _resolve_transitions,
    _screen_summary,
)

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


# --- Duplicate-screen collapse (classify_screens -> _resolve_screen_roles) ---
#
# The bug these cover, observed on a real signup flow: a researcher uploaded the
# same "add your email" step twice (placeholder vs. filled-in). infer_transitions
# then put the flow's incoming edge on one twin and every outgoing edge on the
# other, so only 3 of 12 screens were reachable from the start and no participant
# could ever finish the task.

UNFILLED_ID = uuid.uuid4()
FILLED_ID = uuid.uuid4()
PASSWORD_ID = uuid.uuid4()
UNFILLED_CTA_ID = uuid.uuid4()
FILLED_CTA_ID = uuid.uuid4()


def _twin_screen(screen_id, screen_key, cta_id) -> ScreenModel:
    return ScreenModel(
        id=screen_id,
        stimulus_id=uuid.uuid4(),
        screen_key=screen_key,
        width=390,
        height=844,
        elements=[
            UIElementModel(
                id=cta_id,
                screen_id=screen_id,
                element_key="create_account_button",
                type="button",
                text="Create an account",
                bbox=[20, 700, 370, 756],
                properties={"semantic_role": "primary_action", "interactable": True},
            )
        ],
    )


def _twin_screens() -> list[ScreenModel]:
    return [
        _twin_screen(UNFILLED_ID, "email_unfilled", UNFILLED_CTA_ID),
        _twin_screen(FILLED_ID, "email_unfilled_1", FILLED_CTA_ID),
        ScreenModel(
            id=PASSWORD_ID,
            stimulus_id=uuid.uuid4(),
            screen_key="password",
            width=390,
            height=844,
            elements=[],
        ),
    ]


def _role(screen_key, role="step", duplicate_of=None, summary="s") -> ScreenRole:
    return ScreenRole(screen_key=screen_key, summary=summary, role=role, duplicate_of=duplicate_of)


def test_resolve_screen_roles_keeps_a_backwards_duplicate_link():
    roles = _resolve_screen_roles(
        _twin_screens(),
        [_role("email_unfilled"), _role("email_unfilled_1", duplicate_of="email_unfilled")],
    )

    assert roles["email_unfilled_1"]["duplicate_of"] == "email_unfilled"


def test_resolve_screen_roles_drops_a_forwards_duplicate_link():
    """duplicate_of may only point at an earlier screen — that's what keeps the
    collapse acyclic and independent of the order the model listed screens in."""
    roles = _resolve_screen_roles(
        _twin_screens(), [_role("email_unfilled", duplicate_of="email_unfilled_1")]
    )

    assert roles["email_unfilled"]["duplicate_of"] is None


def test_resolve_screen_roles_drops_an_unknown_screen_and_duplicate_target():
    roles = _resolve_screen_roles(
        _twin_screens(),
        [_role("ghost_screen"), _role("email_unfilled_1", duplicate_of="also_not_real")],
    )

    assert "ghost_screen" not in roles
    assert roles["email_unfilled_1"]["duplicate_of"] is None


def test_resolve_screen_roles_keeps_only_the_earliest_entry_and_latest_success():
    roles = _resolve_screen_roles(
        _twin_screens(),
        [
            _role("email_unfilled", role="entry"),
            _role("email_unfilled_1", role="entry"),
            _role("password", role="success"),
        ],
    )

    assert roles["email_unfilled"]["role"] == "entry"
    assert roles["email_unfilled_1"]["role"] == "step"
    assert roles["password"]["role"] == "success"


def test_canonical_screen_keys_follows_a_duplicate_chain_to_its_root():
    roles = {
        "a": {"duplicate_of": None},
        "b": {"duplicate_of": "a"},
        "c": {"duplicate_of": "b"},
    }

    assert _canonical_screen_keys(roles) == {"a": "a", "b": "a", "c": "a"}


def test_resolve_transitions_reconnects_a_flow_severed_across_duplicate_twins():
    """The actual repair: an edge leaving the filled twin is re-homed onto the
    unfilled twin's own same-keyed element, so the screen that the flow arrives
    at is also the screen the flow can leave from."""
    screens = _twin_screens()
    canonical = {"email_unfilled": "email_unfilled", "email_unfilled_1": "email_unfilled"}

    transitions = _resolve_transitions(
        screens,
        [
            InferredTransition(
                from_screen_key="email_unfilled_1",
                element_key="create_account_button",
                action="CLICK",
                to_screen_key="password",
            )
        ],
        canonical,
    )

    assert transitions == [
        {
            "from_screen_id": UNFILLED_ID,
            "trigger_element_id": UNFILLED_CTA_ID,
            "action": "CLICK",
            "to_screen_id": PASSWORD_ID,
        }
    ]


def test_resolve_transitions_drops_an_edge_that_collapses_into_a_self_loop():
    """An edge between two renderings of one screen described a re-render, not
    navigation — persisting it would make the merged screen link to itself."""
    screens = _twin_screens()
    canonical = {"email_unfilled": "email_unfilled", "email_unfilled_1": "email_unfilled"}

    transitions = _resolve_transitions(
        screens,
        [
            InferredTransition(
                from_screen_key="email_unfilled",
                element_key="create_account_button",
                action="CLICK",
                to_screen_key="email_unfilled_1",
            )
        ],
        canonical,
    )

    assert transitions == []


def test_resolve_transitions_drops_a_remapped_edge_whose_trigger_has_no_counterpart():
    """execute_action matches transitions against elements of the screen the
    participant is standing on, so an edge whose trigger doesn't exist on the
    surviving twin could never fire — dropping beats persisting a dead edge."""
    screens = _twin_screens()
    screens[1].elements[0].element_key = "only_on_the_filled_twin"
    canonical = {"email_unfilled": "email_unfilled", "email_unfilled_1": "email_unfilled"}

    transitions = _resolve_transitions(
        screens,
        [
            InferredTransition(
                from_screen_key="email_unfilled_1",
                element_key="only_on_the_filled_twin",
                action="CLICK",
                to_screen_key="password",
            )
        ],
        canonical,
    )

    assert transitions == []
