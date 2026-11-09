"""Find up to three genuinely different routes for a trip.

TomTom's alternatives come first. Its docs warn that it may return fewer than
requested, so any shortfall is filled by routing through waypoints placed to
either side of the trip's midpoint.
"""

from collections.abc import Iterator
from datetime import datetime
from typing import Protocol

from routing.domain import LatLon, Route, RoutingError
from routing.geometry import destination_point, haversine_m, initial_bearing_deg

TARGET_ROUTE_COUNT = 3
ROAD_CELL_DEGREES = 0.005
MAX_SHARED_ROAD = 0.9
DETOUR_OFFSET_FRACTIONS = (0.15, 0.30)
MAX_DETOUR_DURATION_RATIO = 2.0


class RouteProvider(Protocol):
    def calculate_routes(
        self,
        origin: LatLon,
        destination: LatLon,
        departure: datetime,
        load_lb: float,
        via: LatLon | None = None,
        max_alternatives: int = 0,
    ) -> list[Route]: ...


def _road_cells(route: Route) -> set[tuple[int, int]]:
    return {
        (round(point.lat / ROAD_CELL_DEGREES), round(point.lon / ROAD_CELL_DEGREES))
        for point in route.points
    }


class _DistinctRoutes:
    def __init__(self) -> None:
        self.routes: list[Route] = []
        self._cells: list[set[tuple[int, int]]] = []

    def add(self, route: Route) -> None:
        """Keep the route only if it differs enough from every route kept so far."""
        cells = _road_cells(route)
        for existing in self._cells:
            shared = len(cells & existing) / min(len(cells), len(existing))
            if shared >= MAX_SHARED_ROAD:
                return
        self.routes.append(route)
        self._cells.append(cells)


def detour_waypoints(origin: LatLon, destination: LatLon) -> Iterator[LatLon]:
    """Yield points beside the trip's midpoint, nearest first, alternating sides."""
    trip_m = haversine_m(origin, destination)
    bearing = initial_bearing_deg(origin, destination)
    midpoint = destination_point(origin, bearing, trip_m / 2)
    for fraction in DETOUR_OFFSET_FRACTIONS:
        for side in (90, -90):
            yield destination_point(midpoint, bearing + side, trip_m * fraction)


def find_route_options(
    provider: RouteProvider,
    origin: LatLon,
    destination: LatLon,
    departure: datetime,
    load_lb: float,
) -> list[Route]:
    """Return up to three distinct routes, with the provider's best route first."""
    found = _DistinctRoutes()
    for route in provider.calculate_routes(
        origin, destination, departure, load_lb, max_alternatives=TARGET_ROUTE_COUNT - 1
    ):
        found.add(route)

    longest_allowed_s = found.routes[0].duration_s * MAX_DETOUR_DURATION_RATIO
    for waypoint in detour_waypoints(origin, destination):
        if len(found.routes) >= TARGET_ROUTE_COUNT:
            break
        try:
            detour = provider.calculate_routes(origin, destination, departure, load_lb, via=waypoint)[0]
        except RoutingError:
            # A waypoint can land somewhere undrivable. The routes already found are still valid.
            continue
        if detour.duration_s <= longest_allowed_s:
            found.add(detour)

    return found.routes[:TARGET_ROUTE_COUNT]
