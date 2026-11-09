from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from routing.domain import LatLon
from routing.geometry import mercator_y
from trips import heatmap as heatmap_module
from trips.heatmap import (
    FORECAST_HOURS,
    GRID_OPTIONS,
    MAX_CELLS,
    Heatmap,
    build_heatmap,
    choose_cells,
    corridor_cells,
)
from trips.tests.helpers import FakeWeather, forecast_from
from weather.forecast import LocationForecast

START = datetime(2026, 11, 10, 0, 0, tzinfo=UTC)
DEPARTURE = START + timedelta(hours=3)
SHORT_PATH = [LatLon(40.0, -100.0), LatLon(40.0, -99.5)]
LONG_PATHS = [
    [LatLon(40.7, -74.0), LatLon(41.5, -90.0), LatLon(40.0, -105.0), LatLon(34.0, -118.2)],
    [LatLon(40.7, -74.0), LatLon(36.0, -86.0), LatLon(35.0, -106.0), LatLon(34.0, -118.2)],
    [LatLon(40.7, -74.0), LatLon(33.0, -84.0), LatLon(32.0, -106.0), LatLon(34.0, -118.2)],
]


def calm(position: LatLon) -> LocationForecast:
    return forecast_from(START)


def build(by_position: Any = calm, paths: Any = None, **overrides: Any) -> tuple[Heatmap, FakeWeather]:
    weather = FakeWeather(by_position)
    values: dict[str, Any] = {"departure": DEPARTURE, "load_lb": 20_000}
    result = build_heatmap(paths or [SHORT_PATH], weather=weather, **{**values, **overrides})
    return result, weather


def test_short_trips_use_the_finest_grid() -> None:
    assert choose_cells([SHORT_PATH])[0] == GRID_OPTIONS[0][0]


def test_long_trips_use_a_coarser_grid_within_the_budget() -> None:
    size, cells = choose_cells(LONG_PATHS)

    assert size > GRID_OPTIONS[0][0]
    assert len(cells) <= MAX_CELLS


def test_a_grid_that_exactly_fits_the_budget_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    finest_size, finest_radius = GRID_OPTIONS[0]
    count = len(corridor_cells([SHORT_PATH], finest_size, finest_radius))

    monkeypatch.setattr(heatmap_module, "MAX_CELLS", count)
    assert choose_cells([SHORT_PATH])[0] == finest_size

    monkeypatch.setattr(heatmap_module, "MAX_CELLS", count - 1)
    assert choose_cells([SHORT_PATH])[0] > finest_size


def test_coarsest_grid_is_the_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(heatmap_module, "MAX_CELLS", 0)

    assert choose_cells([SHORT_PATH])[0] == GRID_OPTIONS[-1][0]


def test_grid_options_widen_from_fine_to_coarse() -> None:
    sizes = [size for size, _ in GRID_OPTIONS]

    assert sizes == sorted(sizes)
    assert all(radius >= 1 for _, radius in GRID_OPTIONS)


def test_long_straight_sections_leave_no_gaps() -> None:
    path = [LatLon(0, 0), LatLon(0, 10)]

    cells = corridor_cells([path], 0.25, 0)

    assert cells == {(column, 0) for column in range(41)}


def test_diagonal_sections_leave_no_gaps() -> None:
    cells = corridor_cells([[LatLon(0, 0), LatLon(5, 5)]], 0.5, 0)

    columns = sorted(column for column, _ in cells)
    assert set(columns) == set(range(11))


def test_corridor_is_a_disc_around_the_route() -> None:
    point = LatLon(0, 0)

    cells = corridor_cells([[point, point]], 1.0, 2)

    assert len(cells) == 13
    assert (2, 0) in cells
    assert (0, -2) in cells
    assert (1, 1) in cells
    assert (2, 1) not in cells
    assert (2, 2) not in cells


def test_corridor_covers_every_route() -> None:
    first = [LatLon(0, 0), LatLon(0, 1)]
    second = [LatLon(0, 5), LatLon(0, 6)]

    cells = corridor_cells([first, second], 1.0, 0)

    assert cells == {(0, 0), (1, 0), (5, 0), (6, 0)}


def test_rows_are_spaced_in_mercator_not_degrees() -> None:
    point = LatLon(60, 0)

    assert corridor_cells([[point, point]], 1.0, 0) == {(0, round(mercator_y(60)))}


def test_every_frame_covers_every_corridor_cell() -> None:
    result, _ = build()

    assert len(result.frames) == FORECAST_HOURS == 49
    assert {len(frame) for frame in result.frames} == {len(result.cells)}


def test_cells_are_unique_and_inside_the_grid() -> None:
    result, _ = build()

    assert len(set(result.cells)) == len(result.cells)
    assert result.cells == sorted(result.cells)
    assert all(0 <= cell < result.columns * result.rows for cell in result.cells)


def test_grid_cells_are_square_on_the_map() -> None:
    result, _ = build()

    width = (result.east - result.west) / result.columns
    height = (mercator_y(result.north) - mercator_y(result.south)) / result.rows
    assert width == pytest.approx(height)


def test_cell_indexes_match_the_positions_used_for_the_weather() -> None:
    result, weather = build()

    positions = weather.calls[0]
    assert len(positions) == len(result.cells)
    width = (result.east - result.west) / result.columns
    height = (mercator_y(result.north) - mercator_y(result.south)) / result.rows
    for index, position in zip(result.cells, positions, strict=True):
        row, column = divmod(index, result.columns)
        assert position.lon == pytest.approx(result.west + (column + 0.5) * width)
        assert mercator_y(position.lat) == pytest.approx(mercator_y(result.north) - (row + 0.5) * height)


def test_all_positions_are_requested_together_once() -> None:
    assert len(build()[1].calls) == 1


def test_grid_contains_the_route() -> None:
    result, _ = build()

    for point in SHORT_PATH:
        assert result.west <= point.lon <= result.east
        assert result.south <= point.lat <= result.north


def test_cell_centers_are_shared_between_trips() -> None:
    _, first = build(paths=[SHORT_PATH])
    _, second = build(paths=[[LatLon(40.0, -99.8), LatLon(40.0, -99.2)]])

    assert set(first.calls[0]) & set(second.calls[0])


def test_each_frame_reads_the_forecast_for_its_hour() -> None:
    # Wind passes 25 mph when the slider reaches hour 10, which is forecast hour 13.
    result, _ = build(lambda position: forecast_from(START, wind=lambda hour: 30.0 if hour >= 13 else 5.0))

    assert set(result.frames[9]) == {"0"}
    assert set(result.frames[10]) == {"1"}
    assert set(result.frames[48]) == {"1"}


def test_first_frame_is_the_departure_time() -> None:
    result, _ = build(lambda position: forecast_from(START, wind=lambda hour: 30.0 if hour == 3 else 5.0))

    assert set(result.frames[0]) == {"1"}
    assert set(result.frames[1]) == {"0"}


def test_precipitation_comes_from_the_hour_starting_at_each_frame() -> None:
    # Forecast index 8 is the total for 07:00-08:00, which is slider hour 4 (departure 03:00).
    result, _ = build(lambda position: forecast_from(START, rain=lambda hour: 0.3 if hour == 8 else 0.0))

    assert set(result.frames[3]) == {"0"}
    assert set(result.frames[4]) == {"2"}
    assert set(result.frames[5]) == {"0"}


def test_departure_offset_is_respected() -> None:
    chicago = timezone(timedelta(hours=-6))
    local = DEPARTURE.astimezone(chicago)

    first, _ = build(lambda position: forecast_from(START, wind=lambda hour: float(hour)))
    second, _ = build(lambda position: forecast_from(START, wind=lambda hour: float(hour)), departure=local)

    assert first.frames == second.frames


def test_slider_hours_stay_exact_across_a_daylight_saving_change() -> None:
    chicago_start = datetime(2026, 10, 31, 23, 0, tzinfo=UTC)
    forecast = forecast_from(chicago_start, wind=lambda hour: 30.0 if hour == 20 else 5.0)

    departure = chicago_start.astimezone(ZoneInfo("America/Chicago"))
    result, _ = build(lambda position: forecast, departure=departure)

    assert set(result.frames[20]) == {"1"}
    assert set(result.frames[19]) == {"0"}


def test_load_rules_use_the_entered_load() -> None:
    def windy(position: LatLon) -> LocationForecast:
        return forecast_from(START, wind=lambda hour: 47.0)

    assert set(build(windy, load_lb=30_000)[0].frames[0]) == {"3"}
    assert set(build(windy, load_lb=30_001)[0].frames[0]) == {"4"}


def test_each_cell_uses_its_own_forecast() -> None:
    midpoint = -99.75

    def by_position(position: LatLon) -> LocationForecast:
        return forecast_from(START, snow=lambda hour: 2.5 if position.lon > midpoint else 0.0)

    result, weather = build(by_position)

    for code, position in zip(result.frames[0], weather.calls[0], strict=True):
        assert code == ("3" if position.lon > midpoint else "0")


def test_hours_past_the_end_of_the_forecast_are_not_shown_as_calm() -> None:
    # 20 forecast hours: the slider can use wind up to 19 and precipitation up to hour 18.
    result, _ = build(lambda position: forecast_from(START, hours=20))

    assert set(result.frames[15]) == {"0"}
    assert set(result.frames[16]) == {"-"}
    assert set(result.frames[48]) == {"-"}


def test_missing_values_are_not_shown_as_calm() -> None:
    base = forecast_from(START)
    wind = list(base.wind_mph)
    wind[3] = None
    gap = LocationForecast(base.timezone, base.first_hour, tuple(wind), base.rain_in_hr, base.snow_in_hr)

    result, _ = build(lambda position: gap)

    assert set(result.frames[0]) == {"-"}
    assert set(result.frames[1]) == {"0"}
