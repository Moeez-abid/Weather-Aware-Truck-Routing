from dataclasses import dataclass
from typing import NamedTuple


class LatLon(NamedTuple):
    lat: float
    lon: float


@dataclass(frozen=True)
class Place:
    label: str
    position: LatLon


@dataclass(frozen=True)
class TimingPoint:
    """How far along the route a point is, in distance and in driving time."""

    point_index: int
    distance_m: float
    elapsed_s: float


@dataclass(frozen=True)
class Route:
    points: tuple[LatLon, ...]
    distance_m: float
    duration_s: float
    timing: tuple[TimingPoint, ...]


class RoutingError(Exception):
    """Base class. Messages are safe to show to users."""


class NoRouteError(RoutingError):
    """The provider worked, but no drivable route exists for these locations."""


class ProviderError(RoutingError):
    """The routing provider failed or could not be reached."""
