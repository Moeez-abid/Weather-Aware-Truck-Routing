"""Fake providers and small builders shared by the planner and endpoint tests."""

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from routing.domain import LatLon, NoRouteError, Route, TimingPoint
from weather.forecast import LocationForecast

METERS_PER_MILE = 1609.344
ORIGIN = LatLon(40.0, -100.0)
DESTINATION = LatLon(40.0, -95.0)


def straight_route(miles: float, hours: float, lat: float = 40.0) -> Route:
    """A straight route. Using a different latitude makes a distinct route."""
    points = tuple(LatLon(lat, -100 + i * 0.05) for i in range(101))
    length = miles * METERS_PER_MILE
    return Route(
        points=points,
        distance_m=length,
        duration_s=hours * 3600,
        timing=(TimingPoint(0, 0, 0), TimingPoint(100, length, hours * 3600)),
    )


def forecast_from(
    start: datetime,
    hours: int = 400,
    wind: Callable[[int], float] = lambda hour: 5.0,
    rain: Callable[[int], float] = lambda hour: 0.0,
    snow: Callable[[int], float] = lambda hour: 0.0,
    timezone: str = "America/Chicago",
) -> LocationForecast:
    return LocationForecast(
        timezone=timezone,
        first_hour=int(start.timestamp()),
        wind_mph=tuple(wind(hour) for hour in range(hours)),
        rain_in_hr=tuple(rain(hour) for hour in range(hours)),
        snow_in_hr=tuple(snow(hour) for hour in range(hours)),
    )


class FakeRouter:
    def __init__(self, routes: Sequence[Route]) -> None:
        self.routes = list(routes)
        self.calls: list[dict[str, Any]] = []

    def calculate_routes(
        self,
        origin: LatLon,
        destination: LatLon,
        departure: datetime,
        load_lb: float,
        via: LatLon | None = None,
        max_alternatives: int = 0,
        timeout_s: float | None = None,
    ) -> list[Route]:
        self.calls.append({"departure": departure, "load_lb": load_lb, "via": via})
        if via is not None:
            raise NoRouteError("No detour here.")
        return self.routes


class FakeWeather:
    """Answers each position with `by_position(position)`, and records what was asked for."""

    def __init__(self, by_position: Callable[[LatLon], LocationForecast]) -> None:
        self.by_position = by_position
        self.calls: list[list[LatLon]] = []

    def forecasts(self, positions: Sequence[LatLon]) -> list[LocationForecast]:
        self.calls.append(list(positions))
        return [self.by_position(position) for position in positions]
