"""Plan a trip: find routes, read the weather at each ETA, score them and pick the best."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import chain
from string import ascii_uppercase
from typing import Protocol
from zoneinfo import ZoneInfo

from risk.classification import RiskAssessment, WeatherSample, assess
from risk.recommendation import (
    CheckpointRisk,
    Recommendation,
    RouteRiskSummary,
    recommend,
    summarize_route,
)
from routing.checkpoints import Checkpoint, sample_checkpoints
from routing.domain import LatLon, Route
from routing.options import RouteProvider, find_route_options
from weather.forecast import LocationForecast

# The form defaults to the current time, which is slightly in the past once it is submitted.
DEPARTURE_GRACE = timedelta(minutes=15)

CHECKPOINT_INTERVALS_MILES = (10, 25, 50)
# Each checkpoint costs one Open-Meteo call, and the free tier allows 600 a minute and 10,000 a
# day for everyone using the app. 450 still fits three coast-to-coast routes checked every 25
# miles, while a single long trip checked every 10 miles (over 1,000 calls) is turned away.
MAX_CHECKPOINTS = 450


class InvalidDepartureError(Exception):
    """The departure time can't be used. The message is safe to show to users."""


class TripTooLongError(Exception):
    """The trip needs more weather checks than one request may use. The message is safe to show.

    `interval_miles` is the smallest checkpoint interval that would fit, if any does.
    """

    def __init__(self, message: str, interval_miles: int | None) -> None:
        super().__init__(message)
        self.interval_miles = interval_miles


class WeatherProvider(Protocol):
    def forecasts(self, positions: Sequence[LatLon]) -> list[LocationForecast]: ...


@dataclass(frozen=True)
class TripRequest:
    origin: LatLon
    destination: LatLon
    local_departure: datetime
    load_lb: float
    interval_miles: int


@dataclass(frozen=True)
class PlannedCheckpoint:
    checkpoint: Checkpoint
    timezone: str
    weather: WeatherSample
    risk: RiskAssessment


@dataclass(frozen=True)
class PlannedRoute:
    id: str
    route: Route
    checkpoints: list[PlannedCheckpoint]
    summary: RouteRiskSummary


@dataclass(frozen=True)
class TripPlan:
    departure: datetime
    timezone: str
    routes: list[PlannedRoute]
    recommendation: Recommendation
    # False when the routes leave out road closures planned for the departure. See routing.options.
    closures_checked: bool = True


def _resolve_departure(
    local_departure: datetime, origin_forecast: LocationForecast, now: datetime
) -> datetime:
    departure = local_departure.replace(tzinfo=ZoneInfo(origin_forecast.timezone))
    if departure < now - DEPARTURE_GRACE:
        raise InvalidDepartureError("Departure time is in the past.")
    # Raises if the forecast can't reach the departure, before any routing calls are spent.
    origin_forecast.sample_at(departure)
    # UTC because adding hours to a local time would ignore a daylight saving change on the way.
    return departure.astimezone(UTC)


def _plan_route(
    route_id: str,
    route: Route,
    checkpoints: Sequence[Checkpoint],
    forecasts: Sequence[LocationForecast],
    load_lb: float,
) -> PlannedRoute:
    planned = []
    for checkpoint, forecast in zip(checkpoints, forecasts, strict=True):
        weather = forecast.sample_at(checkpoint.eta)
        planned.append(PlannedCheckpoint(checkpoint, forecast.timezone, weather, assess(weather, load_lb)))

    summary = summarize_route(
        route_id,
        [CheckpointRisk(item.checkpoint.mile, item.risk.level) for item in planned],
        route.duration_s,
    )
    return PlannedRoute(route_id, route, planned, summary)


def _check_checkpoint_count(
    routes: Sequence[Route],
    sampled: Sequence[Sequence[Checkpoint]],
    interval_miles: int,
    departure: datetime,
) -> None:
    """Raise before any weather calls are spent if the trip needs too many checkpoints."""
    needed = sum(len(checkpoints) for checkpoints in sampled)
    if needed <= MAX_CHECKPOINTS:
        return

    for wider in (interval for interval in CHECKPOINT_INTERVALS_MILES if interval > interval_miles):
        if sum(len(sample_checkpoints(route, wider, departure)) for route in routes) <= MAX_CHECKPOINTS:
            raise TripTooLongError(
                f"Checking the weather every {interval_miles} miles on this trip takes {needed} "
                f"checks, and the limit is {MAX_CHECKPOINTS}. Choose {wider} miles instead.",
                wider,
            )
    raise TripTooLongError(
        f"This trip is too long to check the weather along: it takes {needed} checks, and the "
        f"limit is {MAX_CHECKPOINTS}. Try a shorter trip.",
        None,
    )


def plan_trip(
    trip: TripRequest,
    router: RouteProvider,
    weather: WeatherProvider,
    now: datetime | None = None,
) -> TripPlan:
    origin_forecast = weather.forecasts([trip.origin])[0]
    departure = _resolve_departure(
        trip.local_departure, origin_forecast, now or datetime.now(UTC)
    )

    options = find_route_options(router, trip.origin, trip.destination, departure, trip.load_lb)
    routes = options.routes
    sampled = [sample_checkpoints(route, trip.interval_miles, departure) for route in routes]
    _check_checkpoint_count(routes, sampled, trip.interval_miles, departure)
    forecasts = weather.forecasts([item.position for item in chain.from_iterable(sampled)])

    planned_routes = []
    start = 0
    for index, (route, checkpoints) in enumerate(zip(routes, sampled, strict=True)):
        end = start + len(checkpoints)
        planned_routes.append(
            _plan_route(ascii_uppercase[index], route, checkpoints, forecasts[start:end], trip.load_lb)
        )
        start = end

    return TripPlan(
        departure=departure,
        timezone=origin_forecast.timezone,
        routes=planned_routes,
        recommendation=recommend([route.summary for route in planned_routes]),
        closures_checked=options.closures_checked,
    )
