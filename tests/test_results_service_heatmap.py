import uuid

from app.services.results_service import _gaussian_kernel, _smooth_and_normalize


def test_gaussian_kernel_peaks_at_its_own_center():
    kernel = _gaussian_kernel(radius=2, sigma=1.2)
    center = kernel[2][2]
    for y, row in enumerate(kernel):
        for x, value in enumerate(row):
            if (y, x) != (2, 2):
                assert value < center


def test_gaussian_kernel_is_symmetric():
    kernel = _gaussian_kernel(radius=2, sigma=1.2)
    size = len(kernel)
    for y in range(size):
        for x in range(size):
            assert kernel[y][x] == kernel[size - 1 - y][size - 1 - x]


def test_smooth_and_normalize_peaks_at_1_on_the_hottest_cell():
    size = 8
    grid = [[0.0] * size for _ in range(size)]
    grid[4][4] = 1000.0

    smoothed = _smooth_and_normalize(grid, size)

    assert smoothed[4][4] == 1.0
    assert max(v for row in smoothed for v in row) == 1.0


def test_smooth_and_normalize_spreads_intensity_to_neighboring_cells():
    """The whole point of Gaussian smoothing: a single hot cell's intensity
    bleeds into its neighbors rather than staying an isolated spike."""
    size = 8
    grid = [[0.0] * size for _ in range(size)]
    grid[4][4] = 1000.0

    smoothed = _smooth_and_normalize(grid, size)

    assert smoothed[4][5] > 0.0
    assert smoothed[5][4] > 0.0
    assert smoothed[3][4] > 0.0
    # Strictly less than the peak — a neighbor was never observed directly.
    assert smoothed[4][5] < smoothed[4][4]


def test_smooth_and_normalize_handles_an_all_zero_grid_without_crashing():
    size = 4
    grid = [[0.0] * size for _ in range(size)]

    smoothed = _smooth_and_normalize(grid, size)

    assert all(value == 0.0 for row in smoothed for value in row)


def test_smooth_and_normalize_is_symmetric_for_a_centered_hot_cell():
    """Two equidistant cells from a single source should end up with equal
    smoothed intensity — asserts the convolution isn't accidentally biased
    toward one axis/direction."""
    size = 9
    grid = [[0.0] * size for _ in range(size)]
    grid[4][4] = 1000.0

    smoothed = _smooth_and_normalize(grid, size)

    assert smoothed[4][5] == smoothed[4][3] == smoothed[5][4] == smoothed[3][4]


# --- get_completion_rates (run-history list, planning/02-api.md) ---


class _FakeCompletionRateSession:
    """Mimics session.execute(...) returning (run_id, value) pairs — enough to
    verify get_completion_rates fills in None for a run with no completion_rate
    metric yet, rather than omitting it or fabricating 0.0."""

    def __init__(self, rows):
        self._rows = rows

    async def execute(self, _stmt):
        return self._rows


async def test_get_completion_rates_defaults_a_missing_run_to_none():
    from app.services.results_service import ResultsService

    run_with_metric = uuid.uuid4()
    run_without_metric = uuid.uuid4()
    session = _FakeCompletionRateSession([(run_with_metric, 0.72)])
    service = ResultsService(session)

    rates = await service.get_completion_rates([run_with_metric, run_without_metric])

    assert rates == {run_with_metric: 0.72, run_without_metric: None}


async def test_get_completion_rates_short_circuits_on_an_empty_list():
    from app.services.results_service import ResultsService

    service = ResultsService(session=None)

    assert await service.get_completion_rates([]) == {}
