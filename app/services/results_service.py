import math
import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    HumanBenchmarkModel,
    InsightModel,
    MetricModel,
    ObservationModel,
    ParticipantRunModel,
    PatternModel,
    ScreenModel,
    SegmentResultModel,
    UIElementModel,
    ValidationResultModel,
)

# MVP grid resolution for get_pixel_heatmap — per-screen, not global, since
# screens have their own width/height. Not user-configurable yet; a finer
# grid is a straightforward later change (see that method's docstring).
HEATMAP_GRID_SIZE = 32
_GAUSSIAN_RADIUS = 2
_GAUSSIAN_SIGMA = 1.2
# Matches app/agents/providers/participant_model.py's own _visual_saliency
# fallback — a screen row with no recorded width/height (shouldn't normally
# happen post-analysis, but this is read-only reporting, not a place to 500).
_DEFAULT_SCREEN_SIZE = (390, 844)


def _gaussian_kernel(radius: int, sigma: float) -> list[list[float]]:
    return [
        [math.exp(-(dx * dx + dy * dy) / (2 * sigma * sigma)) for dx in range(-radius, radius + 1)]
        for dy in range(-radius, radius + 1)
    ]


def _smooth_and_normalize(grid: list[list[float]], size: int) -> list[list[float]]:
    """LLD §24's Gaussian-smooth + normalize-intensity steps. Spread-form
    convolution (each source cell distributes its own value outward via the
    kernel) rather than gather-form — equivalent for a symmetric kernel, and
    lets the loop skip every empty cell, which is most of them for a sparse
    gaze grid."""
    kernel = _gaussian_kernel(_GAUSSIAN_RADIUS, _GAUSSIAN_SIGMA)
    kernel_sum = sum(sum(row) for row in kernel)
    smoothed = [[0.0] * size for _ in range(size)]
    for gy in range(size):
        for gx in range(size):
            value = grid[gy][gx]
            if value == 0.0:
                continue
            for ky, krow in enumerate(kernel):
                sy = gy + ky - _GAUSSIAN_RADIUS
                if not (0 <= sy < size):
                    continue
                for kx, weight in enumerate(krow):
                    sx = gx + kx - _GAUSSIAN_RADIUS
                    if not (0 <= sx < size):
                        continue
                    smoothed[sy][sx] += value * weight / kernel_sum
    peak = max((v for row in smoothed for v in row), default=0.0)
    if peak <= 0:
        return smoothed
    return [[v / peak for v in row] for row in smoothed]


class ResultsService:
    """Owns read-only queries over observations/metrics/segments/validation/
    patterns/insights, keyed only by `run_id` — no ownership check (that's
    StudyService + SimulationRunService, composed in
    app/usecases/results.py:ResultsUseCase). Never renders a heatmap or path
    from a screenshot (HLD §1's key rule) — these are real queries against real
    tables; they're empty until the Simulation/Analytics/Validation/InsightModel
    agents (planning/07, 09, 10, 11) actually run."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_participant_runs(self, run_id: uuid.UUID) -> list[ParticipantRunModel]:
        result = await self._session.scalars(
            select(ParticipantRunModel).where(ParticipantRunModel.simulation_run_id == run_id)
        )
        return list(result)

    async def list_observations(
        self, run_id: uuid.UUID, limit: int = 200, offset: int = 0
    ) -> list[ObservationModel]:
        result = await self._session.scalars(
            select(ObservationModel)
            .join(
                ParticipantRunModel, ObservationModel.participant_run_id == ParticipantRunModel.id
            )
            .where(ParticipantRunModel.simulation_run_id == run_id)
            .order_by(ObservationModel.participant_run_id, ObservationModel.sequence_no)
            .limit(limit)
            .offset(offset)
        )
        return list(result)

    async def list_all_observations(self, run_id: uuid.UUID) -> list[ObservationModel]:
        """Unpaginated — for the Analytics Engine's aggregation job
        (planning/09), which needs every observation for the run, not a page of
        them the way the Results API's `list_observations` does."""
        result = await self._session.scalars(
            select(ObservationModel)
            .join(
                ParticipantRunModel, ObservationModel.participant_run_id == ParticipantRunModel.id
            )
            .where(ParticipantRunModel.simulation_run_id == run_id)
            .order_by(ObservationModel.participant_run_id, ObservationModel.sequence_no)
        )
        return list(result)

    async def get_completion_rates(self, run_ids: list[uuid.UUID]) -> dict[uuid.UUID, float | None]:
        """The one number a run-history list needs per row without a full
        `get_metrics` fetch each — `None` (not 0.0) for a run `aggregate_run`
        hasn't reached yet, so a caller can distinguish "not computed" from
        "computed and zero" (a real 100%-abandonment result)."""
        if not run_ids:
            return {}
        result = await self._session.execute(
            select(MetricModel.simulation_run_id, MetricModel.value).where(
                MetricModel.simulation_run_id.in_(run_ids),
                MetricModel.level == "task_success",
                MetricModel.metric == "completion_rate",
            )
        )
        rates = {run_id: value for run_id, value in result}
        return {run_id: rates.get(run_id) for run_id in run_ids}

    async def get_metrics(self, run_id: uuid.UUID) -> dict[str, list[dict]]:
        """Metric rows are dimensioned by screen/element, so several rows share
        one `metric` name and differ only by which screen or element they
        describe. Resolve those ids to their human-readable keys here — a
        caller rendering bare `metric` names would otherwise show a dozen
        identical, indistinguishable `click_rate` entries."""
        result = await self._session.execute(
            select(MetricModel, ScreenModel.screen_key, UIElementModel.element_key)
            .outerjoin(ScreenModel, MetricModel.screen_id == ScreenModel.id)
            .outerjoin(UIElementModel, MetricModel.element_id == UIElementModel.id)
            .where(MetricModel.simulation_run_id == run_id)
        )
        by_level: dict[str, list[dict]] = {
            "task_success": [],
            "friction": [],
            "discoverability": [],
        }
        for metric, screen_key, element_key in result:
            by_level.setdefault(metric.level, []).append(
                {
                    "id": metric.id,
                    "level": metric.level,
                    "metric": metric.metric,
                    "element_id": metric.element_id,
                    "screen_id": metric.screen_id,
                    "element_key": element_key,
                    "screen_key": screen_key,
                    "segment": metric.segment,
                    "value": metric.value,
                    "sample_size": metric.sample_size,
                }
            )
        return by_level

    async def get_heatmap(self, run_id: uuid.UUID) -> list[dict]:
        """LLD §24: aggregate stored GAZE events into spatial bins. Element-level
        binning for the MVP (per LLD §10, pixel-level isn't required)."""
        result = await self._session.execute(
            select(
                ObservationModel.screen_id,
                ObservationModel.element_id,
                func.coalesce(func.sum(ObservationModel.duration_ms), 0).label("intensity"),
                func.count().label("fixation_count"),
            )
            .join(
                ParticipantRunModel, ObservationModel.participant_run_id == ParticipantRunModel.id
            )
            .where(ParticipantRunModel.simulation_run_id == run_id, ObservationModel.type == "GAZE")
            .group_by(ObservationModel.screen_id, ObservationModel.element_id)
        )
        return [
            {
                "screen_id": row.screen_id,
                "element_id": row.element_id,
                "intensity": float(row.intensity),
                "fixation_count": row.fixation_count,
            }
            for row in result
        ]

    async def get_paths(self, run_id: uuid.UUID, sample_size: int = 20) -> list[dict]:
        """LLD §25: sample representative paths rather than rendering every one."""
        participant_runs = await self._session.scalars(
            select(ParticipantRunModel.id)
            .where(ParticipantRunModel.simulation_run_id == run_id)
            .limit(sample_size)
        )
        paths = []
        for pr_id in participant_runs:
            screens = await self._session.scalars(
                select(ObservationModel.screen_id)
                .where(
                    ObservationModel.participant_run_id == pr_id,
                    ObservationModel.type == "SCREEN_ENTER",
                )
                .order_by(ObservationModel.sequence_no)
            )
            paths.append(
                {"participant_run_id": pr_id, "screens": [s for s in screens if s is not None]}
            )
        return paths

    async def get_pixel_heatmap(
        self,
        run_id: uuid.UUID,
        participant_run_ids: list[uuid.UUID] | None = None,
        grid_size: int = HEATMAP_GRID_SIZE,
    ) -> list[dict]:
        """LLD §24's full pipeline (normalize coordinates -> bin -> Gaussian
        smooth -> normalize intensity), which `get_heatmap` above always
        described as a *simpler stand-in* for, never the intended end state.
        Bins real GAZE (x, y) into a per-screen `grid_size` x `grid_size` grid
        (screens have their own width/height, so binning is per-screen, not
        global), weighted by `duration_ms` same as `get_heatmap`, then
        Gaussian-smooths and normalizes to `[0, 1]`. `participant_run_ids`
        optionally scopes this to one audience segment — see
        `ResultsUseCase.get_pixel_heatmap`, which resolves segment membership
        (a cross-Service concern this Service deliberately doesn't own) before
        calling this."""
        conditions = [
            ParticipantRunModel.simulation_run_id == run_id,
            ObservationModel.type == "GAZE",
            ObservationModel.x.is_not(None),
            ObservationModel.y.is_not(None),
            ObservationModel.screen_id.is_not(None),
        ]
        if participant_run_ids is not None:
            conditions.append(ObservationModel.participant_run_id.in_(participant_run_ids))

        result = await self._session.execute(
            select(
                ObservationModel.screen_id,
                ObservationModel.x,
                ObservationModel.y,
                ObservationModel.duration_ms,
            )
            .join(
                ParticipantRunModel, ObservationModel.participant_run_id == ParticipantRunModel.id
            )
            .where(*conditions)
        )
        rows = list(result)
        if not rows:
            return []

        screen_ids = {row.screen_id for row in rows}
        dims_result = await self._session.execute(
            select(ScreenModel.id, ScreenModel.width, ScreenModel.height).where(
                ScreenModel.id.in_(screen_ids)
            )
        )
        dims = {row.id: (row.width or 390, row.height or 844) for row in dims_result}

        grids: dict[uuid.UUID, list[list[float]]] = {}
        for row in rows:
            width, height = dims.get(row.screen_id, _DEFAULT_SCREEN_SIZE)
            grid_x = min(grid_size - 1, max(0, int((row.x / width) * grid_size)))
            grid_y = min(grid_size - 1, max(0, int((row.y / height) * grid_size)))
            grid = grids.setdefault(row.screen_id, [[0.0] * grid_size for _ in range(grid_size)])
            grid[grid_y][grid_x] += row.duration_ms or 1

        cells: list[dict] = []
        for screen_id, grid in grids.items():
            smoothed = _smooth_and_normalize(grid, grid_size)
            for gy in range(grid_size):
                for gx in range(grid_size):
                    intensity = smoothed[gy][gx]
                    if intensity <= 0.0:
                        continue
                    cells.append(
                        {
                            "screen_id": screen_id,
                            "x": (gx + 0.5) / grid_size,
                            "y": (gy + 0.5) / grid_size,
                            "intensity": intensity,
                        }
                    )
        return cells

    async def get_scanpaths(self, run_id: uuid.UUID, sample_size: int = 20) -> list[dict]:
        """The fixation-level companion to `get_paths` above — that method
        returns only the *screens* a sampled participant visited (`SCREEN_ENTER`
        order); this returns every `GAZE`/action event in full chronological
        order with its own coordinates, duration, and (for a scan-gated
        screen) `scan_number`, so a frontend can render the literal ordered
        scanpath a persona took, not just the screens along the way."""
        participant_run_ids = list(
            await self._session.scalars(
                select(ParticipantRunModel.id)
                .where(ParticipantRunModel.simulation_run_id == run_id)
                .limit(sample_size)
            )
        )
        if not participant_run_ids:
            return []

        observations = await self._session.scalars(
            select(ObservationModel)
            .where(
                ObservationModel.participant_run_id.in_(participant_run_ids),
                ObservationModel.type.in_(
                    ("GAZE", "CLICK", "TAP", "SELECT", "OPEN", "SCROLL", "BACK", "TYPE")
                ),
            )
            .order_by(ObservationModel.participant_run_id, ObservationModel.sequence_no)
        )
        by_participant: dict[uuid.UUID, list[dict]] = defaultdict(list)
        for obs in observations:
            by_participant[obs.participant_run_id].append(
                {
                    "sequence_no": obs.sequence_no,
                    "type": obs.type,
                    "screen_id": obs.screen_id,
                    "element_id": obs.element_id,
                    "x": obs.x,
                    "y": obs.y,
                    "duration_ms": obs.duration_ms,
                    "scan_number": (obs.payload or {}).get("scan_number"),
                }
            )
        return [
            {"participant_run_id": pr_id, "path": steps} for pr_id, steps in by_participant.items()
        ]

    async def list_segment_results(self, run_id: uuid.UUID) -> list[SegmentResultModel]:
        result = await self._session.scalars(
            select(SegmentResultModel).where(SegmentResultModel.simulation_run_id == run_id)
        )
        return list(result)

    async def list_patterns(self, run_id: uuid.UUID) -> list[PatternModel]:
        result = await self._session.scalars(
            select(PatternModel).where(PatternModel.simulation_run_id == run_id)
        )
        return list(result)

    async def list_validation_results(self, run_id: uuid.UUID) -> list[ValidationResultModel]:
        result = await self._session.scalars(
            select(ValidationResultModel).where(ValidationResultModel.simulation_run_id == run_id)
        )
        return list(result)

    async def has_human_benchmark(self, study_id: uuid.UUID) -> bool:
        count = await self._session.scalar(
            select(func.count())
            .select_from(HumanBenchmarkModel)
            .where(HumanBenchmarkModel.study_id == study_id)
        )
        return bool(count)

    async def list_insights(self, run_id: uuid.UUID) -> list[InsightModel]:
        result = await self._session.scalars(
            select(InsightModel).where(InsightModel.simulation_run_id == run_id)
        )
        return list(result)
