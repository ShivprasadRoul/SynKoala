import uuid

from app.agents.types import ElementView, ScreenGraph, ScreenView, TransitionView
from app.services.analytics_engine import AnalyticsEngine, ObservationRow, ParticipantRunData

HOME_ID = uuid.uuid4()
CONFIRM_ID = uuid.uuid4()
CTA_ID = uuid.uuid4()
HELP_ID = uuid.uuid4()

P1, P2, P3, P4 = (uuid.uuid4() for _ in range(4))


def _screen_graph() -> ScreenGraph:
    home = ScreenView(
        id=HOME_ID,
        screen_key="home",
        width=390,
        height=844,
        elements=[
            ElementView(
                id=CTA_ID,
                element_key="cta",
                type="button",
                text="Add to cart",
                bbox=(20, 720, 370, 776),
                semantic_role="primary_action",
                interactable=True,
            ),
            ElementView(
                id=HELP_ID,
                element_key="help",
                type="link",
                text="Need help?",
                bbox=(20, 800, 150, 830),
                semantic_role=None,
                interactable=True,
            ),
        ],
    )
    confirm = ScreenView(id=CONFIRM_ID, screen_key="confirm", width=390, height=844, elements=[])
    return ScreenGraph(
        screens={HOME_ID: home, CONFIRM_ID: confirm},
        transitions=[
            TransitionView(
                from_screen_id=HOME_ID,
                trigger_element_id=CTA_ID,
                action="CLICK",
                to_screen_id=CONFIRM_ID,
            )
        ],
    )


def _runs() -> list[ParticipantRunData]:
    p1 = ParticipantRunData(
        id=P1,
        status="COMPLETED",
        task_time_ms=5000.0,
        traits={"digital_confidence": 0.8},
        observations=[
            ObservationRow("SCREEN_ENTER", HOME_ID, None, None, 0),
            ObservationRow("GAZE", HOME_ID, CTA_ID, 500, 1),
            ObservationRow("CLICK", HOME_ID, CTA_ID, None, 2),
            ObservationRow("SCREEN_ENTER", CONFIRM_ID, None, None, 3),
        ],
    )
    p2 = ParticipantRunData(
        id=P2,
        status="ABANDONED",
        task_time_ms=None,
        traits={"digital_confidence": 0.2},
        observations=[
            ObservationRow("SCREEN_ENTER", HOME_ID, None, None, 0),
            ObservationRow("GAZE", HOME_ID, HELP_ID, 300, 1),
            ObservationRow("BACK", None, None, None, 2),
            ObservationRow("SCREEN_ENTER", HOME_ID, None, None, 3),
        ],
    )
    p3 = ParticipantRunData(
        id=P3,
        status="COMPLETED",
        task_time_ms=7000.0,
        traits={"digital_confidence": 0.6},
        observations=[
            ObservationRow("SCREEN_ENTER", HOME_ID, None, None, 0),
            ObservationRow("GAZE", HOME_ID, CTA_ID, 200, 1),
            ObservationRow("GAZE", HOME_ID, CTA_ID, 100, 2),
            ObservationRow("CLICK", HOME_ID, CTA_ID, None, 3),
            ObservationRow("SCREEN_ENTER", CONFIRM_ID, None, None, 4),
        ],
    )
    p4 = ParticipantRunData(
        id=P4,
        status="FAILED",
        task_time_ms=None,
        traits=None,
        observations=[ObservationRow("SCREEN_ENTER", HOME_ID, None, None, 0)],
    )
    return [p1, p2, p3, p4]


def _metric(rows, metric, element_id=None, screen_id=None):
    return next(
        r
        for r in rows
        if r.metric == metric and r.element_id == element_id and r.screen_id == screen_id
    )


def _segment(rows, segment, metric):
    return next(r for r in rows if r.segment == segment and r.metric == metric)


class TestShortestPathBaseline:
    def test_returns_one_action_zero_screens_when_critical_element_is_on_start_screen(self):
        engine = AnalyticsEngine()
        assert engine.shortest_path_baseline(_screen_graph(), HOME_ID, ["cta"]) == (1, 0)

    def test_returns_none_without_expected_critical_actions(self):
        engine = AnalyticsEngine()
        assert engine.shortest_path_baseline(_screen_graph(), HOME_ID, None) is None

    def test_bfs_counts_hops_to_reach_a_critical_element_on_a_later_screen(self):
        graph = _screen_graph()
        # Critical element lives on `confirm`, reachable in one hop from `home`.
        graph.screens[CONFIRM_ID].elements.append(
            ElementView(
                id=uuid.uuid4(),
                element_key="confirm_cta",
                type="button",
                text="Confirm",
                bbox=(0, 0, 10, 10),
                semantic_role=None,
                interactable=True,
            )
        )
        engine = AnalyticsEngine()
        assert engine.shortest_path_baseline(graph, HOME_ID, ["confirm_cta"]) == (2, 1)

    def test_returns_none_when_critical_action_is_unreachable(self):
        engine = AnalyticsEngine()
        assert engine.shortest_path_baseline(_screen_graph(), HOME_ID, ["does_not_exist"]) is None


class TestComputeMetrics:
    def test_completion_and_abandonment_rate(self):
        rows = AnalyticsEngine().compute_metrics(_runs(), baseline=None)
        assert _metric(rows, "completion_rate").value == 0.5
        assert _metric(rows, "completion_rate").sample_size == 4
        assert _metric(rows, "abandonment_rate").value == 0.25

    def test_backtrack_rate_counts_participants_with_at_least_one_back(self):
        rows = AnalyticsEngine().compute_metrics(_runs(), baseline=None)
        assert _metric(rows, "backtrack_rate").value == 0.25

    def test_dead_end_rate_is_per_screen_and_uses_final_screen_plus_non_completion(self):
        rows = AnalyticsEngine().compute_metrics(_runs(), baseline=None)
        home_dead_end = _metric(rows, "dead_end_rate", screen_id=HOME_ID)
        confirm_dead_end = _metric(rows, "dead_end_rate", screen_id=CONFIRM_ID)
        assert home_dead_end.value == 0.5  # P2, P4 stuck / 4 reached
        assert home_dead_end.sample_size == 4
        assert confirm_dead_end.value == 0.0  # P1, P3 both completed from there

    def test_click_rate_and_repeated_interaction_rate_for_an_element(self):
        rows = AnalyticsEngine().compute_metrics(_runs(), baseline=None)
        assert _metric(rows, "click_rate", element_id=CTA_ID).value == 1.0
        assert _metric(rows, "click_rate", element_id=CTA_ID).sample_size == 2
        assert _metric(rows, "repeated_interaction_rate", element_id=CTA_ID).value == 0.0

    def test_revisit_rate_reflects_participants_with_2plus_fixations(self):
        rows = AnalyticsEngine().compute_metrics(_runs(), baseline=None)
        # P1 gazed CTA once, P3 gazed CTA twice -> 1 of 2 exposed participants revisited.
        assert _metric(rows, "revisit_rate", element_id=CTA_ID).value == 0.5

    def test_attention_share_is_normalized_across_all_gazed_elements(self):
        rows = AnalyticsEngine().compute_metrics(_runs(), baseline=None)
        cta_share = _metric(rows, "attention_share", element_id=CTA_ID).value
        help_share = _metric(rows, "attention_share", element_id=HELP_ID).value
        assert round(cta_share + help_share, 6) == 1.0
        assert round(cta_share, 4) == round(800 / 1100, 4)

    def test_first_attention_rate_is_over_total_participants(self):
        rows = AnalyticsEngine().compute_metrics(_runs(), baseline=None)
        assert _metric(rows, "first_attention_rate", element_id=CTA_ID).value == 0.5
        assert _metric(rows, "first_attention_rate", element_id=HELP_ID).value == 0.25

    def test_hesitation_time_averages_dwell_before_first_interaction(self):
        rows = AnalyticsEngine().compute_metrics(_runs(), baseline=None)
        # P1: 500ms before its one CLICK. P3: 200+100=300ms before its CLICK. mean=400.
        assert _metric(rows, "hesitation_time", element_id=CTA_ID).value == 400.0

    def test_excess_actions_and_screens_use_the_shortest_path_baseline(self):
        rows = AnalyticsEngine().compute_metrics(_runs(), baseline=(1, 0))
        assert _metric(rows, "excess_actions").value == -0.25
        assert _metric(rows, "excess_screens").value == 1.75

    def test_excess_actions_and_screens_are_skipped_without_a_baseline(self):
        rows = AnalyticsEngine().compute_metrics(_runs(), baseline=None)
        assert not [r for r in rows if r.metric in ("excess_actions", "excess_screens")]

    def test_empty_run_list_produces_no_metrics(self):
        assert AnalyticsEngine().compute_metrics([], baseline=None) == []


class TestComputeSegments:
    def test_splits_by_trait_threshold_and_excludes_traitless_runs(self):
        rows = AnalyticsEngine().compute_segments(_runs(), critical_element_ids={CTA_ID})
        segments = {r.segment for r in rows}
        assert segments == {"digital_confidence_low", "digital_confidence_high"}

    def test_low_segment_aggregate_values(self):
        rows = AnalyticsEngine().compute_segments(_runs(), critical_element_ids={CTA_ID})
        assert _segment(rows, "digital_confidence_low", "completion_rate").value == 0.0
        assert _segment(rows, "digital_confidence_low", "abandonment_rate").value == 1.0
        assert _segment(rows, "digital_confidence_low", "backtrack_rate").value == 1.0
        assert _segment(rows, "digital_confidence_low", "click_rate").value == 0.0
        assert _segment(rows, "digital_confidence_low", "first_attention_rate").value == 0.0

    def test_high_segment_aggregate_values(self):
        rows = AnalyticsEngine().compute_segments(_runs(), critical_element_ids={CTA_ID})
        assert _segment(rows, "digital_confidence_high", "completion_rate").value == 1.0
        assert _segment(rows, "digital_confidence_high", "abandonment_rate").value == 0.0
        assert _segment(rows, "digital_confidence_high", "backtrack_rate").value == 0.0
        assert _segment(rows, "digital_confidence_high", "click_rate").value == 1.0
        assert _segment(rows, "digital_confidence_high", "first_attention_rate").value == 1.0
        assert _segment(rows, "digital_confidence_high", "task_time_ms").value == 6000.0

    def test_first_attention_rate_is_skipped_without_critical_elements(self):
        rows = AnalyticsEngine().compute_segments(_runs(), critical_element_ids=None)
        assert not [r for r in rows if r.metric == "first_attention_rate"]
