import uuid
from unittest.mock import AsyncMock, Mock

from app.agents.providers.vision_provider import InferredTransition, ScreenRole
from app.db.models import ScreenModel, UIElementModel
from app.workers.jobs import analyze_stimulus as job_module
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


# --- _reachable_screen_ids / _infer_best_transitions (LLM non-determinism) --
#
# Reproduced live: the same infer_transitions call, given the same input, can
# return a fully-connected flow on one attempt and a severed one (an edge
# only into the entry screen, none out of it) on another — a study published
# with the severed version put every participant into a guaranteed 100%
# drop-off. Retrying and keeping the best-connected attempt is the fix.

HOME2_ID = uuid.uuid4()
CHECKOUT_ID = uuid.uuid4()
CONFIRM2_ID = uuid.uuid4()
CTA2_ID = uuid.uuid4()
PAY_ID = uuid.uuid4()


def _linear_flow_screens() -> list[ScreenModel]:
    return [
        ScreenModel(
            id=HOME2_ID,
            stimulus_id=uuid.uuid4(),
            screen_key="home",
            width=None,
            height=None,
            elements=[
                UIElementModel(
                    id=CTA2_ID,
                    screen_id=HOME2_ID,
                    element_key="checkout_button",
                    type="button",
                    text="Checkout",
                    bbox=[0, 0, 10, 10],
                    properties={"semantic_role": "primary_action", "interactable": True},
                )
            ],
        ),
        ScreenModel(
            id=CHECKOUT_ID,
            stimulus_id=uuid.uuid4(),
            screen_key="checkout",
            width=None,
            height=None,
            elements=[
                UIElementModel(
                    id=PAY_ID,
                    screen_id=CHECKOUT_ID,
                    element_key="pay_button",
                    type="button",
                    text="Pay",
                    bbox=[0, 0, 10, 10],
                    properties={"semantic_role": "primary_action", "interactable": True},
                )
            ],
        ),
        ScreenModel(
            id=CONFIRM2_ID,
            stimulus_id=uuid.uuid4(),
            screen_key="confirm",
            width=None,
            height=None,
            elements=[],
        ),
    ]


class _QueuedProvider:
    """Returns one canned ScreenGraphInference per call, in order — stands in
    for a real vision model whose infer_transitions output varies call to
    call given identical input."""

    def __init__(self, responses):
        from app.agents.providers.vision_provider import ScreenGraphInference

        self._responses = [ScreenGraphInference(transitions=t) for t in responses]
        self.calls = 0

    async def infer_transitions(self, _screens):
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response


def test_reachable_screen_ids_follows_resolved_edges_from_the_entry_screen():
    screens = _linear_flow_screens()
    transitions = [
        {"from_screen_id": HOME2_ID, "to_screen_id": CHECKOUT_ID},
        {"from_screen_id": CHECKOUT_ID, "to_screen_id": CONFIRM2_ID},
    ]

    reached = job_module._reachable_screen_ids(screens, transitions, "home")

    assert reached == {HOME2_ID, CHECKOUT_ID, CONFIRM2_ID}


def test_reachable_screen_ids_returns_empty_for_an_unknown_start_key():
    screens = _linear_flow_screens()

    assert job_module._reachable_screen_ids(screens, [], "nonexistent") == set()


async def test_infer_best_transitions_retries_past_a_severed_first_attempt():
    """The exact scenario reproduced live: attempt 1 connects nothing past the
    entry screen (home has no edge out at all in this attempt); attempt 2 is
    the complete chain. The severed attempt must not be what gets persisted
    just because it came first."""
    screens = _linear_flow_screens()
    canonical = {"home": "home", "checkout": "checkout", "confirm": "confirm"}
    severed = []  # no edges at all out of home on the first attempt
    complete = [
        InferredTransition(
            from_screen_key="home",
            element_key="checkout_button",
            action="CLICK",
            to_screen_key="checkout",
        ),
        InferredTransition(
            from_screen_key="checkout",
            element_key="pay_button",
            action="CLICK",
            to_screen_key="confirm",
        ),
    ]
    provider = _QueuedProvider([severed, complete])

    transitions = await job_module._infer_best_transitions(
        provider, screens, screens, canonical, entry_key="home", success_key="confirm"
    )

    assert provider.calls == 2
    reached = job_module._reachable_screen_ids(screens, transitions, "home")
    assert reached == {HOME2_ID, CHECKOUT_ID, CONFIRM2_ID}


async def test_infer_best_transitions_stops_early_once_success_is_reached():
    screens = _linear_flow_screens()
    canonical = {"home": "home", "checkout": "checkout", "confirm": "confirm"}
    complete = [
        InferredTransition(
            from_screen_key="home",
            element_key="checkout_button",
            action="CLICK",
            to_screen_key="checkout",
        ),
        InferredTransition(
            from_screen_key="checkout",
            element_key="pay_button",
            action="CLICK",
            to_screen_key="confirm",
        ),
    ]
    # A second canned response that would fail the assertion below if ever
    # consumed — proves the loop stopped after the first, already-successful
    # attempt rather than spending a second call regardless.
    provider = _QueuedProvider([complete, []])

    transitions = await job_module._infer_best_transitions(
        provider, screens, screens, canonical, entry_key="home", success_key="confirm"
    )

    assert provider.calls == 1
    assert len(transitions) == 2


async def test_infer_best_transitions_makes_one_call_without_a_known_entry_screen():
    screens = _linear_flow_screens()
    canonical = {"home": "home", "checkout": "checkout", "confirm": "confirm"}
    provider = _QueuedProvider([[]])

    await job_module._infer_best_transitions(
        provider, screens, screens, canonical, entry_key=None, success_key=None
    )

    assert provider.calls == 1


# --- classify/infer only runs once all sibling screens are analyzed ---
#
# request_analysis enqueues one analyze_stimulus job per stimulus, and a
# multi-screenshot upload is one stimulus per screen — a 12-screen upload
# fires 12 of these jobs. classify_screens/infer_transitions used to re-run
# on every single one, wasting up to 11 redundant whole-study LLM calls and
# racing each other's replace_transitions_for_study writes. Only the job
# that finds every sibling screen already analyzed should actually run it.


class _FakeStimuliService:
    def __init__(self, stimulus, all_screens):
        self._stimulus = stimulus
        self._all_screens = all_screens
        self.classify_calls = 0
        self.save_roles_calls = 0
        self.replace_transitions_calls = 0

    async def get_with_screens(self, _stimulus_id):
        return self._stimulus

    async def list_screens_for_study(self, _study_id):
        return self._all_screens

    async def save_screen_analysis(self, screen, elements, raw_analysis):
        screen.analysis = raw_analysis
        screen.elements = [
            Mock(
                **e,
                properties={"semantic_role": e["semantic_role"], "interactable": e["interactable"]},
            )
            for e in elements
        ]

    async def save_screen_roles(self, screens, roles):
        self.save_roles_calls += 1

    async def replace_transitions_for_study(self, study_id, transitions):
        self.replace_transitions_calls += 1


class _FakeProvider:
    def __init__(self):
        self.classify_calls = 0
        self.infer_calls = 0

    async def analyze_screen(self, image, content_type, image_size=None):
        from app.agents.providers.vision_provider import ScreenAnalysis

        return ScreenAnalysis(elements=[])

    async def classify_screens(self, screens):
        from app.agents.providers.vision_provider import ScreenRoleInference

        self.classify_calls += 1
        return ScreenRoleInference(screens=[])

    async def infer_transitions(self, screens):
        from app.agents.providers.vision_provider import ScreenGraphInference

        self.infer_calls += 1
        return ScreenGraphInference(transitions=[])


async def test_handle_analyze_stimulus_skips_classify_while_a_sibling_screen_is_unanalyzed(
    monkeypatch,
):
    unanalyzed_sibling = ScreenModel(
        id=uuid.uuid4(), stimulus_id=uuid.uuid4(), screen_key="other", elements=[], analysis=None
    )
    this_screen = ScreenModel(
        id=uuid.uuid4(),
        stimulus_id=uuid.uuid4(),
        screen_key="this_one",
        elements=[],
        analysis=None,
        image_url="stimuli/x/original",
    )
    stimulus = Mock(id=uuid.uuid4(), study_id=uuid.uuid4(), screens=[this_screen])
    fake_stimuli = _FakeStimuliService(stimulus, all_screens=[this_screen, unanalyzed_sibling])
    fake_provider = _FakeProvider()

    monkeypatch.setattr(job_module, "StimulusService", lambda session: fake_stimuli)
    monkeypatch.setattr(job_module, "PydanticAIVisionProvider", lambda: fake_provider)
    monkeypatch.setattr(
        job_module, "download_object", AsyncMock(return_value=(b"bytes", "image/png"))
    )

    await job_module.handle_analyze_stimulus(
        session=None, payload={"stimulus_id": str(stimulus.id)}
    )

    assert this_screen.analysis is not None  # this job's own screen was still analyzed
    assert fake_provider.classify_calls == 0
    assert fake_provider.infer_calls == 0
    assert fake_stimuli.replace_transitions_calls == 0


async def test_handle_analyze_stimulus_runs_classify_once_every_sibling_is_analyzed(monkeypatch):
    already_analyzed_sibling = ScreenModel(
        id=uuid.uuid4(),
        stimulus_id=uuid.uuid4(),
        screen_key="other",
        elements=[],
        analysis={"elements": []},
    )
    this_screen = ScreenModel(
        id=uuid.uuid4(),
        stimulus_id=uuid.uuid4(),
        screen_key="this_one",
        elements=[],
        analysis=None,
        image_url="stimuli/x/original",
    )
    stimulus = Mock(id=uuid.uuid4(), study_id=uuid.uuid4(), screens=[this_screen])
    fake_stimuli = _FakeStimuliService(
        stimulus, all_screens=[this_screen, already_analyzed_sibling]
    )
    fake_provider = _FakeProvider()

    monkeypatch.setattr(job_module, "StimulusService", lambda session: fake_stimuli)
    monkeypatch.setattr(job_module, "PydanticAIVisionProvider", lambda: fake_provider)
    monkeypatch.setattr(
        job_module, "download_object", AsyncMock(return_value=(b"bytes", "image/png"))
    )

    await job_module.handle_analyze_stimulus(
        session=None, payload={"stimulus_id": str(stimulus.id)}
    )

    assert fake_provider.classify_calls == 1
    assert fake_provider.infer_calls == 1
    assert fake_stimuli.replace_transitions_calls == 1
