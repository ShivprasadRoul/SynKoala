"""planning/09-analytics-engine.md (HLD §3.H, LLD §14 Aggregation Algorithms, §15
Audience Segment Analysis).

Pure computation over already-fetched rows — no session/DB access, mirroring
`AudienceEngine`'s split from its Service (planning/04): the job handler
(`app/workers/jobs/aggregate_run.py`) does the fetching and persisting, this
class only computes. Metric names match LLD §14's formula names exactly, since
the Validation Engine and Insight Engine (planning/10, 11) will query `metrics`/
`segment_results` rows by name.

Heatmap/scanpath rendering (this doc's item 5, LLD §24-25) is deliberately not
here: `ResultsService.get_heatmap`/`get_paths` (planning/02's Results resource)
already aggregate `observations` into spatial bins / sampled paths at read time.
That's a simpler pipeline than LLD §24's full normalize->bin->Gaussian-smooth->
normalize-intensity chain, but it satisfies the one rule that actually has no
exceptions (HLD §1): never computed client-side, never invented by a model.
Swapping in real Gaussian smoothing later doesn't change anything in this file.
"""

import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from statistics import mean

from app.agents.types import ScreenGraph

# The Simulation Engine's `ActionType` (app/agents/providers/participant_model.py)
# plus TAP, which only ever appears in HUMAN-sourced observations (planning/13) —
# an "interaction" for friction/discoverability purposes either way.
ACTION_TYPES = frozenset({"CLICK", "TAP", "SCROLL", "BACK", "OPEN", "SELECT", "TYPE"})

# LLD §15's own example (`digital_confidence < 0.5` / `>= 0.5`) — applied to every
# trait present, not just digital_confidence.
SEGMENT_THRESHOLD = 0.5


@dataclass
class ObservationRow:
    type: str
    screen_id: uuid.UUID | None
    element_id: uuid.UUID | None
    duration_ms: int | None
    sequence_no: int


@dataclass
class ParticipantRunData:
    """One `participant_runs` row's worth of input, already resolved by the job
    handler. `traits` is `None` for a HUMAN run's tester sessions (no sampled
    `participants` row to draw from) — those are excluded from segmentation but
    still counted in every run-wide metric."""

    id: uuid.UUID
    status: str
    task_time_ms: float | None
    traits: dict[str, float] | None
    observations: list[ObservationRow] = field(default_factory=list)


@dataclass
class MetricRow:
    level: str
    metric: str
    value: float
    sample_size: int
    element_id: uuid.UUID | None = None
    screen_id: uuid.UUID | None = None


@dataclass
class SegmentRow:
    segment: str
    metric: str
    value: float
    sample_size: int


class AnalyticsEngine:
    """planning/09-analytics-engine.md. Stateless — every method is a pure
    function of its arguments, so it needs no `__init__`."""

    # ---- Excess actions/screens baseline (LLD §14) ----

    def shortest_path_baseline(
        self,
        screen_graph: ScreenGraph,
        start_screen_id: uuid.UUID,
        critical_actions: list[str] | None,
    ) -> tuple[int, int] | None:
        """BFS over the screen graph for the minimum actions/screens needed to
        reach one of the task's `expected_critical_actions` from
        `start_screen_id` — the "no-friction" baseline `excess_actions`/
        `excess_screens` are measured against. One extra action always accounts
        for actually triggering the critical element itself (clicking it isn't
        free, even when it's already on the starting screen). Returns `None`
        when the task declares no critical actions, or they're unreachable in
        the analyzed graph — skipped, not fabricated, same as an absent
        `human_benchmarks` row."""
        critical = set(critical_actions or [])
        if not critical or start_screen_id not in screen_graph.screens:
            return None

        def _has_critical(screen_id: uuid.UUID) -> bool:
            screen = screen_graph.screens.get(screen_id)
            if screen is None:
                return False
            return any(
                {element.element_key, element.semantic_role or ""} & critical
                for element in screen.elements
            )

        if _has_critical(start_screen_id):
            return (1, 0)

        visited = {start_screen_id}
        queue: deque[tuple[uuid.UUID, int]] = deque([(start_screen_id, 0)])
        while queue:
            screen_id, hops = queue.popleft()
            for transition in screen_graph.transitions_from(screen_id):
                if transition.to_screen_id in visited:
                    continue
                visited.add(transition.to_screen_id)
                next_hops = hops + 1
                if _has_critical(transition.to_screen_id):
                    return (next_hops + 1, next_hops)
                queue.append((transition.to_screen_id, next_hops))
        return None

    # ---- Task success / friction / discoverability (LLD §14) ----

    def compute_metrics(
        self,
        runs: list[ParticipantRunData],
        baseline: tuple[int, int] | None,
    ) -> list[MetricRow]:
        if not runs:
            return []
        rows: list[MetricRow] = [self._completion_rate(runs), self._abandonment_rate(runs)]
        backtrack_row = self._backtrack_rate(runs)
        if backtrack_row is not None:
            rows.append(backtrack_row)
        rows.extend(self._dead_end_rates(runs))
        rows.extend(self._element_interaction_metrics(runs))
        rows.extend(self._excess_actions_and_screens(runs, baseline))
        return rows

    def _completion_rate(self, runs: list[ParticipantRunData]) -> MetricRow:
        completed = sum(1 for r in runs if r.status == "COMPLETED")
        return MetricRow("task_success", "completion_rate", completed / len(runs), len(runs))

    def _abandonment_rate(self, runs: list[ParticipantRunData]) -> MetricRow:
        abandoned = sum(1 for r in runs if r.status == "ABANDONED")
        return MetricRow("task_success", "abandonment_rate", abandoned / len(runs), len(runs))

    def _backtrack_rate(self, runs: list[ParticipantRunData]) -> MetricRow | None:
        with_backtrack = sum(1 for r in runs if any(o.type == "BACK" for o in r.observations))
        return MetricRow("friction", "backtrack_rate", with_backtrack / len(runs), len(runs))

    def _dead_end_rates(self, runs: list[ParticipantRunData]) -> list[MetricRow]:
        """`dead_end_rate(screen) = participants_who_reached_screen_with_no_
        further_progress / participants_who_reached_screen`. "No further
        progress" is approximated as: this screen was the participant's *last*
        `SCREEN_ENTER` and the run didn't end in `COMPLETED` — the data actually
        available (`final_outcome`/`current_screen_id`) rather than re-deriving
        the simulation graph's own per-step dead-end detection."""
        reached: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        stuck: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        for r in runs:
            last_screen: uuid.UUID | None = None
            last_seq = -1
            for obs in r.observations:
                if obs.type != "SCREEN_ENTER" or obs.screen_id is None:
                    continue
                reached[obs.screen_id].add(r.id)
                if obs.sequence_no > last_seq:
                    last_seq, last_screen = obs.sequence_no, obs.screen_id
            if last_screen is not None and r.status != "COMPLETED":
                stuck[last_screen].add(r.id)
        return [
            MetricRow(
                "friction",
                "dead_end_rate",
                len(stuck.get(screen_id, set())) / len(participants),
                len(participants),
                screen_id=screen_id,
            )
            for screen_id, participants in reached.items()
            if participants
        ]

    def _element_interaction_metrics(self, runs: list[ParticipantRunData]) -> list[MetricRow]:
        """Computes `repeated_interaction_rate`, `hesitation_time`, `click_rate`,
        `revisit_rate`, `attention_share`, and `first_attention_rate` together —
        all of them fold over the same per-participant, per-element observation
        scan, so splitting them into separate passes would just mean re-walking
        the same data six times."""
        exposed: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        interacted: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        interacted_2plus: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        gazed: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        gazed_2plus: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        total_dwell: dict[uuid.UUID, float] = defaultdict(float)
        hesitation_samples: dict[uuid.UUID, list[float]] = defaultdict(list)
        first_gaze_seq: dict[uuid.UUID, int] = {}
        first_gaze_element: dict[uuid.UUID, uuid.UUID] = {}
        grand_total_dwell = 0.0

        for r in runs:
            interaction_counts: dict[uuid.UUID, int] = defaultdict(int)
            gaze_counts: dict[uuid.UUID, int] = defaultdict(int)
            first_action_seq: dict[uuid.UUID, int] = {}
            gaze_before: dict[uuid.UUID, list[tuple[int, int]]] = defaultdict(list)

            for obs in r.observations:
                if obs.element_id is None:
                    continue
                exposed[obs.element_id].add(r.id)
                if obs.type == "GAZE":
                    dwell = obs.duration_ms or 0
                    gaze_counts[obs.element_id] += 1
                    total_dwell[obs.element_id] += dwell
                    grand_total_dwell += dwell
                    gaze_before[obs.element_id].append((obs.sequence_no, dwell))
                    gazed[obs.element_id].add(r.id)
                    if r.id not in first_gaze_seq or obs.sequence_no < first_gaze_seq[r.id]:
                        first_gaze_seq[r.id] = obs.sequence_no
                        first_gaze_element[r.id] = obs.element_id
                elif obs.type in ACTION_TYPES:
                    interaction_counts[obs.element_id] += 1
                    if obs.element_id not in first_action_seq:
                        first_action_seq[obs.element_id] = obs.sequence_no

            for element_id, count in interaction_counts.items():
                interacted[element_id].add(r.id)
                if count >= 2:
                    interacted_2plus[element_id].add(r.id)
            for element_id, count in gaze_counts.items():
                if count >= 2:
                    gazed_2plus[element_id].add(r.id)
            for element_id, first_seq in first_action_seq.items():
                dwell_before = sum(
                    d for seq, d in gaze_before.get(element_id, []) if seq < first_seq
                )
                hesitation_samples[element_id].append(dwell_before)

        rows: list[MetricRow] = []
        for element_id, exposed_participants in exposed.items():
            n = len(exposed_participants)
            if n == 0:
                continue
            rows.append(
                MetricRow(
                    "discoverability",
                    "click_rate",
                    len(interacted.get(element_id, set())) / n,
                    n,
                    element_id=element_id,
                )
            )
            rows.append(
                MetricRow(
                    "friction",
                    "repeated_interaction_rate",
                    len(interacted_2plus.get(element_id, set())) / n,
                    n,
                    element_id=element_id,
                )
            )
        for element_id, gazed_participants in gazed.items():
            n = len(gazed_participants)
            if n == 0:
                continue
            rows.append(
                MetricRow(
                    "discoverability",
                    "revisit_rate",
                    len(gazed_2plus.get(element_id, set())) / n,
                    n,
                    element_id=element_id,
                )
            )
        if grand_total_dwell > 0:
            for element_id, dwell in total_dwell.items():
                rows.append(
                    MetricRow(
                        "discoverability",
                        "attention_share",
                        dwell / grand_total_dwell,
                        len(runs),
                        element_id=element_id,
                    )
                )
        if runs:
            first_counts: dict[uuid.UUID, int] = defaultdict(int)
            for element_id in first_gaze_element.values():
                first_counts[element_id] += 1
            for element_id, count in first_counts.items():
                rows.append(
                    MetricRow(
                        "discoverability",
                        "first_attention_rate",
                        count / len(runs),
                        len(runs),
                        element_id=element_id,
                    )
                )
        for element_id, samples in hesitation_samples.items():
            if samples:
                rows.append(
                    MetricRow(
                        "friction",
                        "hesitation_time",
                        mean(samples),
                        len(samples),
                        element_id=element_id,
                    )
                )
        return rows

    def _excess_actions_and_screens(
        self, runs: list[ParticipantRunData], baseline: tuple[int, int] | None
    ) -> list[MetricRow]:
        if baseline is None:
            return []
        baseline_actions, baseline_screens = baseline
        excess_actions = [
            sum(1 for o in r.observations if o.type in ACTION_TYPES) - baseline_actions
            for r in runs
        ]
        excess_screens = [
            sum(1 for o in r.observations if o.type == "SCREEN_ENTER") - baseline_screens
            for r in runs
        ]
        return [
            MetricRow("friction", "excess_actions", mean(excess_actions), len(excess_actions)),
            MetricRow("friction", "excess_screens", mean(excess_screens), len(excess_screens)),
        ]

    # ---- Audience Segment Analysis (LLD §15) ----

    def compute_segments(
        self,
        runs: list[ParticipantRunData],
        critical_element_ids: set[uuid.UUID] | None,
    ) -> list[SegmentRow]:
        """Splits the population by every participant trait actually present, at
        its midpoint (LLD §15's own `digital_confidence < 0.5` / `>= 0.5`
        example). Runs with no `traits` (HUMAN tester sessions) are excluded —
        segmentation is an audience-definition concept and a tester was never
        sampled from one."""
        trait_keys: set[str] = set()
        for r in runs:
            if r.traits:
                trait_keys.update(r.traits.keys())

        rows: list[SegmentRow] = []
        for trait in sorted(trait_keys):
            low = [r for r in runs if r.traits and r.traits.get(trait, 0.0) < SEGMENT_THRESHOLD]
            high = [r for r in runs if r.traits and r.traits.get(trait, 0.0) >= SEGMENT_THRESHOLD]
            for label, members in ((f"{trait}_low", low), (f"{trait}_high", high)):
                if not members:
                    continue
                for metric, value, sample_size in self._segment_aggregate_values(
                    members, critical_element_ids
                ):
                    rows.append(SegmentRow(label, metric, value, sample_size))
        return rows

    def _segment_aggregate_values(
        self,
        runs: list[ParticipantRunData],
        critical_element_ids: set[uuid.UUID] | None,
    ) -> list[tuple[str, float, int]]:
        """LLD §15's comparison set (Attention, First fixation, Task completion,
        Task time, Click rate, Backtracking, Abandonment) collapsed to one
        population-level number per segment — `segment_results` has no element/
        screen dimension the way `metrics` does."""
        n = len(runs)
        completed = sum(1 for r in runs if r.status == "COMPLETED")
        abandoned = sum(1 for r in runs if r.status == "ABANDONED")
        backtracked = sum(1 for r in runs if any(o.type == "BACK" for o in r.observations))
        clicked = sum(
            1
            for r in runs
            if any(o.type in ACTION_TYPES and o.element_id is not None for o in r.observations)
        )
        task_times = [r.task_time_ms for r in runs if r.task_time_ms is not None]
        total_dwell = sum(
            o.duration_ms or 0 for r in runs for o in r.observations if o.type == "GAZE"
        )

        values: list[tuple[str, float, int]] = [
            ("completion_rate", completed / n, n),
            ("abandonment_rate", abandoned / n, n),
            ("backtrack_rate", backtracked / n, n),
            ("click_rate", clicked / n, n),
        ]
        if task_times:
            values.append(("task_time_ms", mean(task_times), len(task_times)))
        if total_dwell > 0:
            values.append(("attention_dwell_ms", total_dwell / n, n))
        if critical_element_ids:
            first_on_critical = sum(
                1 for r in runs if self._first_gaze_element(r) in critical_element_ids
            )
            values.append(("first_attention_rate", first_on_critical / n, n))
        return values

    def _first_gaze_element(self, run: ParticipantRunData) -> uuid.UUID | None:
        first: uuid.UUID | None = None
        first_seq = None
        for obs in run.observations:
            if obs.type == "GAZE" and obs.element_id is not None:
                if first_seq is None or obs.sequence_no < first_seq:
                    first_seq, first = obs.sequence_no, obs.element_id
        return first
