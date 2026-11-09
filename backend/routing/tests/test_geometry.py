import pytest

from routing.domain import LatLon
from routing.geometry import (
    cumulative_distances_m,
    destination_point,
    haversine_m,
    initial_bearing_deg,
    mercator_latitude,
    mercator_y,
    simplify_path,
)


def test_one_degree_of_latitude_is_about_111_km() -> None:
    assert haversine_m(LatLon(0, 0), LatLon(1, 0)) == pytest.approx(111_195, abs=1)


def test_distance_to_the_same_point_is_zero() -> None:
    assert haversine_m(LatLon(40, -100), LatLon(40, -100)) == 0


def test_cumulative_distances_add_up_along_the_points() -> None:
    points = [LatLon(0, 0), LatLon(1, 0), LatLon(1, 0), LatLon(3, 0)]

    assert cumulative_distances_m(points) == pytest.approx([0, 111_195, 111_195, 333_585], abs=3)


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (LatLon(1, 0), 0),
        (LatLon(0, 1), 90),
        (LatLon(-1, 0), 180),
        (LatLon(0, -1), 270),
    ],
)
def test_compass_bearings(target: LatLon, expected: float) -> None:
    assert initial_bearing_deg(LatLon(0, 0), target) == pytest.approx(expected)


def test_destination_point_lands_where_bearing_and_distance_say() -> None:
    start = LatLon(41.88, -87.63)
    target = LatLon(39.74, -104.99)
    distance = haversine_m(start, target)

    result = destination_point(start, initial_bearing_deg(start, target), distance)

    assert result.lat == pytest.approx(target.lat)
    assert result.lon == pytest.approx(target.lon)


def test_destination_point_wraps_longitude() -> None:
    result = destination_point(LatLon(0, 179.9), 90, 111_195 * 0.2)

    assert result.lon == pytest.approx(-179.9, abs=0.001)


def test_simplify_keeps_short_paths_unchanged() -> None:
    points = [LatLon(0, 0), LatLon(1, 1)]

    assert simplify_path(points, 0.1) == points


def test_simplify_removes_points_on_a_straight_line() -> None:
    points = [LatLon(0, i * 0.1) for i in range(11)]

    assert simplify_path(points, 0.0001) == [points[0], points[-1]]


def test_simplify_keeps_corners() -> None:
    points = [LatLon(0, 0), LatLon(0, 1), LatLon(0, 2), LatLon(1, 2), LatLon(2, 2)]

    assert simplify_path(points, 0.0001) == [LatLon(0, 0), LatLon(0, 2), LatLon(2, 2)]


def test_simplify_compares_distance_with_the_tolerance() -> None:
    points = [LatLon(0, 0), LatLon(0.001, 1), LatLon(0, 2)]

    assert simplify_path(points, 0.002) == [points[0], points[2]]
    assert simplify_path(points, 0.0005) == points


def test_simplify_measures_to_the_segment_not_the_infinite_line() -> None:
    points = [LatLon(0, 0), LatLon(0, 3), LatLon(0, 1)]

    assert LatLon(0, 3) in simplify_path(points, 0.0001)


def test_simplify_handles_paths_that_end_where_they_start() -> None:
    points = [LatLon(0, 0), LatLon(0, 1), LatLon(1, 1), LatLon(0, 0)]

    assert LatLon(1, 1) in simplify_path(points, 0.0001)


def test_simplify_handles_repeated_points() -> None:
    points = [LatLon(0, 0), LatLon(0, 0), LatLon(0, 1), LatLon(0, 1)]

    assert simplify_path(points, 0.0001) == [LatLon(0, 0), LatLon(0, 1)]


@pytest.mark.parametrize("peaks", [(1, 2), (2, 1)])
def test_simplify_keeps_corners_on_both_sides_of_the_widest_one(peaks: tuple[int, int]) -> None:
    points = [LatLon(0, 0), LatLon(peaks[0], 1), LatLon(0, 2), LatLon(peaks[1], 3), LatLon(0, 4)]

    assert simplify_path(points, 0.0001) == points


@pytest.mark.parametrize(
    ("lat", "meters"), [(0, 0), (45, 5_621_521.5), (-45, -5_621_521.5), (60, 8_399_737.9)]
)
def test_mercator_projection_matches_web_mercator(lat: float, meters: float) -> None:
    meters_per_degree = 20_037_508.34 / 180

    assert mercator_y(lat) * meters_per_degree == pytest.approx(meters, abs=1)


@pytest.mark.parametrize("lat", [-80, -33.3, 0, 12.5, 40, 71])
def test_mercator_latitude_reverses_the_projection(lat: float) -> None:
    assert mercator_latitude(mercator_y(lat)) == pytest.approx(lat)
