from datetime import UTC, datetime

import pytest

from routing.domain import LatLon, NoRouteError, ProviderError, Route, RoutingError, TimingPoint
from routing.geometry import destination_point, haversine_m, initial_bearing_deg
from routing.options import detour_waypoints, find_route_options

ORIGIN = LatLon(40, -100)
DESTINATION = LatLon(40, -98)
DEPARTURE = datetime(2026, 11, 10, 15, tzinfo=UTC)
POINT_COUNT = 200


def road(lat: float) -> tuple[LatLon, ...]:
    return tuple(LatLon(lat, -100 + i * 0.01) for i in range(POINT_COUNT))


def route(points: tuple[LatLon, ...], duration_s: float = 3600) -> Route:
    return Route(
        points=points,
        distance_m=1000,
        duration_s=duration_s,
        timing=(
            TimingPoint(0, 0, 0),
            TimingPoint(len(points) - 1, 1000, duration_s),
        ),
    )


def route_on(lat: float, duration_s: float = 3600) -> Route:
    return route(road(lat), duration_s)


def sharing(base: Route, other_lat: float, shared_fraction: float) -> Route:
    shared = round(POINT_COUNT * shared_fraction)
    return route(base.points[:shared] + road(other_lat)[shared:])


class FakeProvider:
    def __init__(self, first: list[Route] | Exception, detours: list[Route | Exception]) -> None:
        self.first = first
        self.detours = list(detours)
        self.calls: list[dict] = []

    def calculate_routes(
        self,
        origin: LatLon,
        destination: LatLon,
        departure: datetime,
        load_lb: float,
        via: LatLon | None = None,
        max_alternatives: int = 0,
    ) -> list[Route]:
        self.calls.append({"via": via, "max_alternatives": max_alternatives, "load_lb": load_lb})
        result = self.first if via is None else self.detours.pop(0)
        if isinstance(result, Exception):
            raise result
        return result if isinstance(result, list) else [result]


def options(provider: FakeProvider) -> list[Route]:
    return find_route_options(provider, ORIGIN, DESTINATION, DEPARTURE, 40_000)


A, B, C, D = (route_on(lat) for lat in (40.0, 41.0, 42.0, 43.0))


def test_three_distinct_routes_need_no_extra_requests() -> None:
    provider = FakeProvider([A, B, C], [])

    assert options(provider) == [A, B, C]
    assert len(provider.calls) == 1
    assert provider.calls[0] == {"via": None, "max_alternatives": 2, "load_lb": 40_000}


def test_missing_route_is_filled_through_a_waypoint() -> None:
    provider = FakeProvider([A, B], [C])

    assert options(provider) == [A, B, C]
    assert provider.calls[1]["via"] is not None
    assert provider.calls[1]["max_alternatives"] == 0


def test_stops_as_soon_as_three_routes_are_found() -> None:
    provider = FakeProvider([A], [B, C, D])

    assert options(provider) == [A, B, C]
    assert len(provider.calls) == 3


def test_near_duplicate_alternative_is_replaced() -> None:
    duplicate = sharing(A, 44.0, 0.95)
    provider = FakeProvider([A, duplicate, B], [C])

    assert options(provider) == [A, B, C]


def test_alternative_that_shares_less_road_is_kept() -> None:
    similar = sharing(A, 44.0, 0.85)
    provider = FakeProvider([A, similar, B], [])

    assert options(provider) == [A, similar, B]


def test_exactly_ninety_percent_shared_counts_as_a_duplicate() -> None:
    duplicate = sharing(A, 44.0, 0.90)
    provider = FakeProvider([A, duplicate, B], [C])

    assert duplicate not in options(provider)


def test_detour_matching_an_existing_route_is_rejected() -> None:
    provider = FakeProvider([A, B], [sharing(B, 44.0, 0.95), C])

    assert options(provider) == [A, B, C]


def test_detour_that_takes_too_long_is_rejected() -> None:
    too_long = route_on(44.0, duration_s=3600 * 2 + 1)
    provider = FakeProvider([A, B], [too_long, C])

    assert options(provider) == [A, B, C]


def test_detour_at_the_duration_limit_is_kept() -> None:
    at_limit = route_on(44.0, duration_s=3600 * 2)
    provider = FakeProvider([A, B], [at_limit])

    assert options(provider) == [A, B, at_limit]


@pytest.mark.parametrize(
    "error", [NoRouteError("undrivable waypoint"), ProviderError("service failed")]
)
def test_failed_waypoints_are_skipped(error: RoutingError) -> None:
    provider = FakeProvider([A, B], [error, C])

    assert options(provider) == [A, B, C]


def test_returns_what_exists_after_trying_every_waypoint() -> None:
    no_route = NoRouteError("none")
    provider = FakeProvider([A], [no_route, no_route, no_route, no_route])

    assert options(provider) == [A]
    assert len(provider.calls) == 5


def test_never_returns_more_than_three_routes() -> None:
    assert options(FakeProvider([A, B, C, D], [])) == [A, B, C]


@pytest.mark.parametrize("error", [NoRouteError("none"), ProviderError("down")])
def test_failure_of_the_main_request_is_raised(error: RoutingError) -> None:
    with pytest.raises(type(error)):
        options(FakeProvider(error, []))


def test_waypoints_sit_on_both_sides_at_two_distances() -> None:
    waypoints = list(detour_waypoints(ORIGIN, DESTINATION))
    trip_m = haversine_m(ORIGIN, DESTINATION)
    midpoint = destination_point(ORIGIN, initial_bearing_deg(ORIGIN, DESTINATION), trip_m / 2)

    assert len(waypoints) == 4
    assert sorted([waypoints[0].lat, midpoint.lat, waypoints[1].lat])[1] == midpoint.lat
    assert sorted([waypoints[2].lat, midpoint.lat, waypoints[3].lat])[1] == midpoint.lat
    for waypoint, fraction in zip(waypoints, (0.15, 0.15, 0.30, 0.30), strict=True):
        assert haversine_m(midpoint, waypoint) == pytest.approx(trip_m * fraction, rel=0.001)
