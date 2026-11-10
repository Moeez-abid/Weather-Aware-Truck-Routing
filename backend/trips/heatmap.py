"""Risk along the trip corridor for every hour of the forecast slider.

Cells are square in Web Mercator, the projection the map is drawn in, so the frontend can
stretch the grid over the map as a single image. Cell centers sit on a fixed lattice, so
different trips share cells and reuse cached forecasts.

Each cell costs one Open-Meteo call, so the finest lattice that stays within the budget is
used: short trips get a detailed grid and long trips a coarser one.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise

from risk.classification import assess
from routing.domain import LatLon
from routing.geometry import mercator_latitude, mercator_y
from trips.planner import InvalidDepartureError, WeatherProvider
from weather.forecast import ForecastUnavailableError, LocationForecast
from weather.open_meteo import FORECAST_DAYS

FORECAST_HOURS = 49
# Cell size in degrees and corridor radius in cells, finest first. Coarse cells are already
# wide, so one ring around the route keeps the corridor about 50 miles to each side.
GRID_OPTIONS = ((0.125, 2), (0.25, 2), (0.5, 2), (1.0, 1), (2.0, 1))
# Leaves room for the trip's own checkpoints within Open-Meteo's limit of 600 calls a minute.
MAX_CELLS = 300
NO_FORECAST = "-"
# The heatmap is requested right after its trip plan, whose departure may already be up to 15
# minutes old. An hour leaves room for a slow connection without allowing old departures.
MAX_DEPARTURE_AGE = timedelta(hours=1)
FORECAST_REACH = timedelta(days=FORECAST_DAYS)


class HeatmapTooLargeError(Exception):
    """Even the coarsest grid needs more cells than one request may use. Safe to show users."""

Cell = tuple[int, int]


@dataclass(frozen=True)
class Heatmap:
    """A grid of `columns` by `rows`, with row 0 at the north edge.

    `cells` lists the flat index (row * columns + column) of each cell in the corridor.
    Each frame is a string with one character per entry in `cells`: the risk level as a
    digit, or NO_FORECAST where the forecast doesn't reach that hour.
    """

    columns: int
    rows: int
    west: float
    south: float
    east: float
    north: float
    cells: list[int]
    frames: list[str]


def _cells_along_path(points: Sequence[tuple[float, float]], size: float) -> set[Cell]:
    cells: set[Cell] = set()
    for (x1, y1), (x2, y2) in pairwise(points):
        # Half-cell steps, so that a long straight section can't skip over a cell.
        steps = max(1, math.ceil(max(abs(x2 - x1), abs(y2 - y1)) / (size / 2)))
        for step in range(steps + 1):
            fraction = step / steps
            cells.add(
                (round((x1 + (x2 - x1) * fraction) / size), round((y1 + (y2 - y1) * fraction) / size))
            )
    return cells


def _widen(cells: set[Cell], radius: int) -> set[Cell]:
    offsets = [
        (dx, dy)
        for dx in range(-radius, radius + 1)
        for dy in range(-radius, radius + 1)
        if dx * dx + dy * dy <= radius * radius
    ]
    return {(x + dx, y + dy) for x, y in cells for dx, dy in offsets}


def _unwrapped_longitudes(path: Sequence[LatLon]) -> list[float]:
    """Longitudes that keep counting past 180 when a path crosses it, instead of jumping to -180.

    Without this, a route crossing the 180th meridian would look like it circles the globe.
    """
    longitudes: list[float] = []
    for point in path:
        lon = point.lon
        if longitudes:
            lon += 360 * round((longitudes[-1] - lon) / 360)
        longitudes.append(lon)
    return longitudes


def _wrapped(lon: float) -> float:
    return (lon + 180) % 360 - 180


def corridor_cells(paths: Sequence[Sequence[LatLon]], size: float, radius: int) -> set[Cell]:
    """Return the (column, row) of every cell near a path. Rows count upward from the equator.

    Columns past the 180th meridian keep counting, so a corridor that crosses it stays together.
    """
    projected = [
        [(lon, mercator_y(point.lat)) for lon, point in zip(_unwrapped_longitudes(path), path)]
        for path in paths
    ]
    on_route = set().union(*(_cells_along_path(path, size) for path in projected))
    return _widen(on_route, radius)


def choose_cells(paths: Sequence[Sequence[LatLon]]) -> tuple[float, set[Cell]]:
    """Return the finest cell size whose corridor fits the budget."""
    for size, radius in GRID_OPTIONS:
        cells = corridor_cells(paths, size, radius)
        if len(cells) <= MAX_CELLS:
            return size, cells
    raise HeatmapTooLargeError(
        "This trip's corridor is too large for the weather heatmap. The route comparison still "
        "uses the forecast at every checkpoint."
    )


def _check_departure(departure: datetime, now: datetime) -> None:
    """Raise before any weather calls are spent if the forecast can't cover the departure."""
    if departure < now - MAX_DEPARTURE_AGE:
        raise InvalidDepartureError("Departure time is in the past.")
    if departure > now + FORECAST_REACH:
        raise InvalidDepartureError("The weather forecast doesn't reach this departure.")


def _risk_code(forecast: LocationForecast, when: datetime, load_lb: float) -> str:
    try:
        return str(int(assess(forecast.sample_at(when), load_lb).level))
    except ForecastUnavailableError:
        # A trip can be valid while the later slider hours run past the end of the forecast.
        return NO_FORECAST


def build_heatmap(
    paths: Sequence[Sequence[LatLon]],
    departure: datetime,
    load_lb: float,
    weather: WeatherProvider,
    now: datetime | None = None,
) -> Heatmap:
    _check_departure(departure, now or datetime.now(UTC))
    size, cells = choose_cells(paths)
    west_column = min(column for column, _ in cells)
    east_column = max(column for column, _ in cells)
    south_row = min(row for _, row in cells)
    north_row = max(row for _, row in cells)
    columns = east_column - west_column + 1

    def flat_index(cell: Cell) -> int:
        return (north_row - cell[1]) * columns + (cell[0] - west_column)

    ordered = sorted(cells, key=flat_index)
    forecasts = weather.forecasts(
        [LatLon(mercator_latitude(row * size), _wrapped(column * size)) for column, row in ordered]
    )

    start = departure.astimezone(UTC)
    moments = [start + timedelta(hours=hour) for hour in range(FORECAST_HOURS)]
    frames = zip(
        *(
            [_risk_code(forecast, moment, load_lb) for moment in moments]
            for forecast in forecasts
        ),
        strict=True,
    )

    return Heatmap(
        columns=columns,
        rows=north_row - south_row + 1,
        west=(west_column - 0.5) * size,
        south=mercator_latitude((south_row - 0.5) * size),
        east=(east_column + 0.5) * size,
        north=mercator_latitude((north_row + 0.5) * size),
        cells=[flat_index(cell) for cell in ordered],
        frames=["".join(frame) for frame in frames],
    )
