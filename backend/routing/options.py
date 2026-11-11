"""Find up to three genuinely different routes for a trip.

TomTom's alternatives come first. Its docs warn that it may return fewer than
requested, so any shortfall is filled by routing through waypoints placed to
either side of the trip's midpoint.

TomTom applies road closures planned for the departure time. A closure on the street at the
origin or destination makes it find no route at all, even though the truck could stop a block
away: arriving in central Houston on Veterans Day did this. When that happens, the trip is routed
again without the departure time, and the plan says that closures weren't checked.
"""

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from routing.domain import LatLon, NoRouteError, Route, RouteTooComplexError, RoutingError
from routing.geometry import destination_point, haversine_m, initial_bearing_deg

TARGET_ROUTE_COUNT = 3
ROAD_CELL_DEGREES = 0.005
MAX_SHARED_ROAD = 0.9
DETOUR_OFFSET_FRACTIONS = (0.15, 0.30)
MAX_DETOUR_DURATION_RATIO = 2.0
# Seconds for all routing calls. The server stops a request at 60 seconds, and the weather
# lookups still need time after routing. Long trips, such as London to Karachi, take TomTom
# 25 to 35 seconds for the main call, so it may use the whole budget, and detours are only
# tried while the budget lasts.
ROUTING_BUDGET_S = 40.0
# A detour call given less time than this would almost always time out.
MIN_DETOUR_S = 5.0


class RouteProvider(Protocol):
    def calculate_routes(
        self,
        origin: LatLon,
        destination: LatLon,
        departure: datetime,
        load_lb: float,
        via: LatLon | None = None,
        max_alternatives: int = 0,
        timeout_s: float | None = None,
        use_departure_time: bool = True,
    ) -> list[Route]: ...


@dataclass(frozen=True)
class RouteOptions:
    routes: list[Route]
    # False when no route respected the closures planned for the departure, so they were left out.
    closures_checked: bool


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


def _main_routes(
    provider: RouteProvider,
    origin: LatLon,
    destination: LatLon,
    departure: datetime,
    load_lb: float,
    deadline: float,
    clock: Callable[[], float],
    use_departure_time: bool,
) -> list[Route]:
    try:
        return provider.calculate_routes(
            origin,
            destination,
            departure,
            load_lb,
            max_alternatives=TARGET_ROUTE_COUNT - 1,
            timeout_s=deadline - clock(),
            use_departure_time=use_departure_time,
        )
    except RouteTooComplexError:
        # Alternatives take TomTom far longer to work out. One route is better than none.
        remaining_s = deadline - clock()
        if remaining_s < MIN_DETOUR_S:
            raise
        return provider.calculate_routes(
            origin,
            destination,
            departure,
            load_lb,
            timeout_s=remaining_s,
            use_departure_time=use_departure_time,
        )


def find_route_options(
    provider: RouteProvider,
    origin: LatLon,
    destination: LatLon,
    departure: datetime,
    load_lb: float,
    clock: Callable[[], float] = time.monotonic,
) -> RouteOptions:
    """Return up to three distinct routes, with the provider's best route first."""
    deadline = clock() + ROUTING_BUDGET_S
    closures_checked = True
    try:
        main_routes = _main_routes(
            provider, origin, destination, departure, load_lb, deadline, clock, True
        )
    except NoRouteError as no_route:
        if deadline - clock() < MIN_DETOUR_S:
            raise
        try:
            main_routes = _main_routes(
                provider, origin, destination, departure, load_lb, deadline, clock, False
            )
        except RoutingError:
            # No closure was the cause, so the first answer stands.
            raise no_route from None
        closures_checked = False

    found = _DistinctRoutes()
    for route in main_routes:
        found.add(route)

    longest_allowed_s = found.routes[0].duration_s * MAX_DETOUR_DURATION_RATIO
    for waypoint in detour_waypoints(origin, destination):
        remaining_s = deadline - clock()
        if len(found.routes) >= TARGET_ROUTE_COUNT or remaining_s < MIN_DETOUR_S:
            break
        try:
            detour = provider.calculate_routes(
                origin,
                destination,
                departure,
                load_lb,
                via=waypoint,
                timeout_s=remaining_s,
                use_departure_time=closures_checked,
            )[0]
        except RoutingError:
            # A waypoint can land somewhere undrivable, or the call can run out of time. The
            # routes already found are still valid.
            continue
        if detour.duration_s <= longest_allowed_s:
            found.add(detour)

    return RouteOptions(found.routes[:TARGET_ROUTE_COUNT], closures_checked)
