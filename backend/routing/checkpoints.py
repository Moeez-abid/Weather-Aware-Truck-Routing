"""Place checkpoints along a route and work out when the truck reaches each one.

TomTom reports cumulative distance and driving time at every maneuver. Between
two maneuvers the truck is assumed to hold a steady speed, so ETAs reflect the
slow city sections and fast highway sections of the actual route.
"""

import math
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from routing.domain import LatLon, Route
from routing.geometry import cumulative_distances_m

METERS_PER_MILE = 1609.344


@dataclass(frozen=True)
class Checkpoint:
    mile: float
    position: LatLon
    elapsed_s: float
    eta: datetime


def checkpoint_miles(total_miles: float, interval_miles: float) -> list[float]:
    """Return the origin, every full interval before the destination, and the destination."""
    interval_count = math.ceil(total_miles / interval_miles)
    return [0.0, *(k * interval_miles for k in range(1, interval_count)), total_miles]


def _point_at(points: Sequence[LatLon], cumulative: Sequence[float], distance_m: float) -> LatLon:
    index = min(bisect_right(cumulative, distance_m) - 1, len(points) - 2)
    span = cumulative[index + 1] - cumulative[index]
    fraction = (distance_m - cumulative[index]) / span if span > 0 else 0
    start, end = points[index], points[index + 1]
    return LatLon(
        start.lat + fraction * (end.lat - start.lat),
        start.lon + fraction * (end.lon - start.lon),
    )


def sample_checkpoints(
    route: Route, interval_miles: float, departure: datetime
) -> list[Checkpoint]:
    if interval_miles <= 0:
        raise ValueError("Checkpoint interval must be positive.")
    if departure.tzinfo is None:
        raise ValueError("Departure time must include a timezone.")

    timing = route.timing
    total_m = timing[-1].distance_m
    if total_m <= 0:
        raise ValueError("Route has no length.")

    offsets = [point.distance_m for point in timing]
    cumulative = cumulative_distances_m(route.points)

    def checkpoint(mile: float, position: LatLon, elapsed_s: float) -> Checkpoint:
        return Checkpoint(mile, position, elapsed_s, departure + timedelta(seconds=elapsed_s))

    def interior_checkpoint(mile: float) -> Checkpoint:
        target_m = mile * METERS_PER_MILE
        index = min(bisect_right(offsets, target_m) - 1, len(timing) - 2)
        start, end = timing[index], timing[index + 1]
        span = end.distance_m - start.distance_m
        fraction = (target_m - start.distance_m) / span if span > 0 else 0

        # TomTom's road length and the length of the drawn line differ slightly,
        # so the position is found by the same fraction of the same section.
        start_m, end_m = cumulative[start.point_index], cumulative[end.point_index]
        position = _point_at(route.points, cumulative, start_m + fraction * (end_m - start_m))
        return checkpoint(
            mile, position, start.elapsed_s + fraction * (end.elapsed_s - start.elapsed_s)
        )

    miles = checkpoint_miles(total_m / METERS_PER_MILE, interval_miles)
    return [
        checkpoint(0.0, route.points[0], 0.0),
        *(interior_checkpoint(mile) for mile in miles[1:-1]),
        checkpoint(miles[-1], route.points[-1], timing[-1].elapsed_s),
    ]
