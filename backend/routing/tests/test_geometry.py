import pytest

from routing.domain import LatLon
from routing.geometry import destination_point, haversine_m, initial_bearing_deg


def test_one_degree_of_latitude_is_about_111_km() -> None:
    assert haversine_m(LatLon(0, 0), LatLon(1, 0)) == pytest.approx(111_195, abs=1)


def test_distance_to_the_same_point_is_zero() -> None:
    assert haversine_m(LatLon(40, -100), LatLon(40, -100)) == 0


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
