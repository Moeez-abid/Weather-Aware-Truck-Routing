import math
from collections.abc import Sequence
from itertools import accumulate, pairwise

from routing.domain import LatLon

EARTH_RADIUS_M = 6_371_008.8


def haversine_m(a: LatLon, b: LatLon) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    h = math.sin((lat2 - lat1) / 2) ** 2 + (
        math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def cumulative_distances_m(points: Sequence[LatLon]) -> list[float]:
    return [0.0, *accumulate(haversine_m(a, b) for a, b in pairwise(points))]


def initial_bearing_deg(a: LatLon, b: LatLon) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return math.degrees(math.atan2(y, x)) % 360


def destination_point(start: LatLon, bearing_deg: float, distance_m: float) -> LatLon:
    angular = distance_m / EARTH_RADIUS_M
    bearing = math.radians(bearing_deg)
    lat1, lon1 = math.radians(start.lat), math.radians(start.lon)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular) + math.cos(lat1) * math.sin(angular) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular) * math.cos(lat1),
        math.cos(angular) - math.sin(lat1) * math.sin(lat2),
    )
    return LatLon(math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180)


def simplify_path(points: Sequence[LatLon], tolerance_deg: float) -> list[LatLon]:
    """Drop points lying within the tolerance of the kept line (Ramer-Douglas-Peucker)."""
    if len(points) < 3:
        return list(points)

    keep = [True, *([False] * (len(points) - 2)), True]
    sections = [(0, len(points) - 1)]
    while sections:
        first, last = sections.pop()
        start, end = points[first], points[last]
        run, rise = end.lon - start.lon, end.lat - start.lat
        length_squared = run * run + rise * rise

        farthest_squared, farthest = tolerance_deg * tolerance_deg, None
        for index in range(first + 1, last):
            x, y = points[index].lon - start.lon, points[index].lat - start.lat
            along = max(0.0, min(1.0, (x * run + y * rise) / length_squared)) if length_squared else 0.0
            distance_squared = (x - along * run) ** 2 + (y - along * rise) ** 2
            if distance_squared > farthest_squared:
                farthest_squared, farthest = distance_squared, index

        if farthest is not None:
            keep[farthest] = True
            sections += [(first, farthest), (farthest, last)]

    return [point for point, kept in zip(points, keep, strict=True) if kept]


def mercator_y(lat: float) -> float:
    """Project a latitude to Web Mercator, in units where one degree of longitude is 1."""
    return math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def mercator_latitude(y: float) -> float:
    return math.degrees(2 * math.atan(math.exp(math.radians(y))) - math.pi / 2)
