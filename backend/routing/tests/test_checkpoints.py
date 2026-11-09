import json
from datetime import UTC, datetime, timedelta, timezone
from itertools import pairwise
from pathlib import Path

import httpx
import pytest

from routing.checkpoints import METERS_PER_MILE, checkpoint_miles, sample_checkpoints
from routing.domain import LatLon, Route, TimingPoint
from routing.geometry import cumulative_distances_m, haversine_m
from routing.tomtom import TomTomClient

DEPARTURE = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
FIXTURES = Path(__file__).parent / "fixtures"


def straight_points(count: int = 101, step_degrees: float = 0.1) -> tuple[LatLon, ...]:
    return tuple(LatLon(0.0, i * step_degrees) for i in range(count))


def steady_route(duration_s: float = 36_000) -> Route:
    points = straight_points()
    length = cumulative_distances_m(points)[-1]
    return Route(
        points=points,
        distance_m=length,
        duration_s=duration_s,
        timing=(
            TimingPoint(0, 0, 0),
            TimingPoint(len(points) - 1, length, duration_s),
        ),
    )


def real_routes(fixture: str) -> list[Route]:
    body = json.loads((FIXTURES / f"{fixture}.json").read_text())
    client = TomTomClient(
        "key", transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    )
    return client.calculate_routes(LatLon(1, 1), LatLon(2, 2), DEPARTURE, 10_000)


@pytest.mark.parametrize(
    ("total", "interval", "expected"),
    [
        (60, 25, [0, 25, 50, 60]),
        (50, 25, [0, 25, 50]),
        (20, 25, [0, 20]),
        (25, 25, [0, 25]),
        (10.5, 10, [0, 10, 10.5]),
        (120, 50, [0, 50, 100, 120]),
        (35, 10, [0, 10, 20, 30, 35]),
    ],
)
def test_checkpoint_miles(total: float, interval: float, expected: list[float]) -> None:
    assert checkpoint_miles(total, interval) == expected


def test_route_length_is_converted_to_statute_miles() -> None:
    route = Route(
        points=straight_points(),
        distance_m=16_093.44,
        duration_s=3600,
        timing=(TimingPoint(0, 0, 0), TimingPoint(100, 16_093.44, 3600)),
    )

    checkpoints = sample_checkpoints(route, 5, DEPARTURE)

    assert [c.mile for c in checkpoints] == pytest.approx([0, 5, 10])


def test_checkpoints_follow_bends_in_the_route() -> None:
    points = (LatLon(0, 0), LatLon(0, 1), LatLon(1, 1))
    leg = haversine_m(points[0], points[1])
    route = Route(
        points=points,
        distance_m=2 * leg,
        duration_s=7200,
        timing=(TimingPoint(0, 0, 0), TimingPoint(2, 2 * leg, 7200)),
    )

    checkpoints = sample_checkpoints(route, (leg / 2) / METERS_PER_MILE, DEPARTURE)

    assert checkpoints[1].position == pytest.approx((0, 0.5), abs=0.001)
    assert checkpoints[2].position == pytest.approx((0, 1), abs=0.001)
    assert checkpoints[3].position == pytest.approx((0.5, 1), abs=0.001)


def test_first_and_last_checkpoints_are_the_trip_ends() -> None:
    route = steady_route()

    checkpoints = sample_checkpoints(route, 25, DEPARTURE)

    assert checkpoints[0].mile == 0
    assert checkpoints[0].position == route.points[0]
    assert checkpoints[0].eta == DEPARTURE
    assert checkpoints[-1].mile == pytest.approx(route.distance_m / METERS_PER_MILE)
    assert checkpoints[-1].position == route.points[-1]
    assert checkpoints[-1].eta == DEPARTURE + timedelta(seconds=36_000)


def test_checkpoints_sit_at_the_requested_distance_along_the_route() -> None:
    route = steady_route()

    checkpoints = sample_checkpoints(route, 25, DEPARTURE)

    for checkpoint in checkpoints:
        travelled_m = haversine_m(route.points[0], checkpoint.position)
        assert travelled_m == pytest.approx(checkpoint.mile * METERS_PER_MILE, abs=0.5)


def test_eta_at_a_steady_speed_is_proportional_to_distance() -> None:
    route = steady_route(duration_s=36_000)
    total_miles = route.distance_m / METERS_PER_MILE

    checkpoint = sample_checkpoints(route, 50, DEPARTURE)[1]

    assert checkpoint.elapsed_s == pytest.approx(36_000 * 50 / total_miles)


def test_eta_follows_the_speed_of_each_section() -> None:
    points = straight_points()
    length = cumulative_distances_m(points)[-1]
    # The first half takes three hours and the second half takes one hour.
    route = Route(
        points=points,
        distance_m=length,
        duration_s=14_400,
        timing=(
            TimingPoint(0, 0, 0),
            TimingPoint(50, length / 2, 10_800),
            TimingPoint(100, length, 14_400),
        ),
    )
    interval = (length / 4) / METERS_PER_MILE

    checkpoints = sample_checkpoints(route, interval, DEPARTURE)

    assert [c.elapsed_s for c in checkpoints] == pytest.approx([0, 5_400, 10_800, 12_600, 14_400])


def test_eta_keeps_the_departure_timezone() -> None:
    chicago = timezone(timedelta(hours=-6))
    departure = datetime(2026, 11, 10, 9, 0, tzinfo=chicago)

    checkpoint = sample_checkpoints(steady_route(), 25, departure)[-1]

    assert checkpoint.eta == departure + timedelta(seconds=36_000)
    assert checkpoint.eta.utcoffset() == timedelta(hours=-6)


def test_position_uses_the_same_section_fraction_when_lengths_differ() -> None:
    points = straight_points()
    geometric_length = cumulative_distances_m(points)[-1]
    road_length = geometric_length * 1.02
    route = Route(
        points=points,
        distance_m=road_length,
        duration_s=3600,
        timing=(TimingPoint(0, 0, 0), TimingPoint(100, road_length, 3600)),
    )
    interval = (road_length / 2) / METERS_PER_MILE * 0.999999

    middle = sample_checkpoints(route, interval, DEPARTURE)[1]

    assert middle.position.lon == pytest.approx(5.0, abs=0.001)


def test_repeated_points_and_offsets_are_handled() -> None:
    first = (LatLon(0, 0), LatLon(0, 1))
    second = (LatLon(0, 1), LatLon(0, 2))
    points = first + second
    half = haversine_m(LatLon(0, 0), LatLon(0, 1))
    route = Route(
        points=points,
        distance_m=2 * half,
        duration_s=7200,
        timing=(
            TimingPoint(0, 0, 0),
            TimingPoint(1, half, 3600),
            TimingPoint(2, half, 3600),
            TimingPoint(3, 2 * half, 7200),
        ),
    )

    checkpoints = sample_checkpoints(route, (half * 0.5) / METERS_PER_MILE, DEPARTURE)

    assert [c.elapsed_s for c in checkpoints] == pytest.approx([0, 1800, 3600, 5400, 7200])
    assert checkpoints[2].position.lon == pytest.approx(1)


@pytest.mark.parametrize("fixture", ["tomtom_routes", "tomtom_via_route"])
def test_real_routes_produce_ordered_checkpoints_on_the_route(fixture: str) -> None:
    for route in real_routes(fixture):
        checkpoints = sample_checkpoints(route, 0.5, DEPARTURE)

        assert len(checkpoints) > 3
        assert checkpoints[-1].elapsed_s == route.duration_s
        for earlier, later in pairwise(checkpoints):
            assert later.mile > earlier.mile
            assert later.elapsed_s >= earlier.elapsed_s
        for checkpoint in checkpoints:
            nearest = min(haversine_m(checkpoint.position, point) for point in route.points)
            assert nearest < 300


@pytest.mark.parametrize("interval", [0, -10])
def test_invalid_interval_is_rejected(interval: float) -> None:
    with pytest.raises(ValueError):
        sample_checkpoints(steady_route(), interval, DEPARTURE)


def test_departure_without_timezone_is_rejected() -> None:
    with pytest.raises(ValueError):
        sample_checkpoints(steady_route(), 25, datetime(2026, 11, 10, 15, 0))


def test_route_without_length_is_rejected() -> None:
    point = LatLon(1, 1)
    route = Route(
        points=(point, point),
        distance_m=0,
        duration_s=0,
        timing=(TimingPoint(0, 0, 0), TimingPoint(1, 0, 0)),
    )

    with pytest.raises(ValueError):
        sample_checkpoints(route, 25, DEPARTURE)
