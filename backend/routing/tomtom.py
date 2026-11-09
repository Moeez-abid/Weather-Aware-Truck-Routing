"""TomTom routing and geocoding.

TomTom only accepts the API key as a query parameter, so request URLs contain
it. Errors raised from here must never include the URL or the original
exception text.
"""

import logging
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any
from urllib.parse import quote

import httpx
from django.conf import settings

from routing.domain import LatLon, NoRouteError, Place, ProviderError, Route, TimingPoint

logger = logging.getLogger(__name__)

BASE_URL = "https://api.tomtom.com"
TIMEOUT_SECONDS = 30
GEOCODE_COUNTRIES = "US,CA,MX"
NO_ROUTE_CODES = {"NO_ROUTE_FOUND", "MAP_MATCHING_FAILURE"}

# TomTom needs the truck's total weight for road limits, but the driver enters only the load.
EMPTY_TRUCK_LB = 33_000
KG_PER_LB = 0.45359237


def gross_weight_kg(load_lb: float) -> int:
    return round((load_lb + EMPTY_TRUCK_LB) * KG_PER_LB)


def _format_position(position: LatLon) -> str:
    return f"{position.lat:.6f},{position.lon:.6f}"


def _format_departure(departure: datetime) -> str:
    if departure.tzinfo is None:
        raise ValueError("Departure time must include a timezone.")
    return departure.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _error_code(response: httpx.Response) -> str | None:
    try:
        return response.json()["detailedError"]["code"]
    except (ValueError, KeyError, TypeError):
        return None


def _parse_route(raw: dict[str, Any]) -> Route:
    # Legs are joined as they are. TomTom's point indexes count the point shared by two legs twice.
    points = tuple(
        LatLon(point["latitude"], point["longitude"]) for leg in raw["legs"] for point in leg["points"]
    )
    timing = tuple(
        TimingPoint(
            point_index=instruction["pointIndex"],
            distance_m=instruction["routeOffsetInMeters"],
            elapsed_s=instruction["travelTimeInSeconds"],
        )
        for instruction in raw["guidance"]["instructions"]
    )
    if len(timing) < 2 or timing[0].point_index != 0 or timing[-1].point_index != len(points) - 1:
        raise ValueError("Route timing does not span the route geometry.")

    return Route(
        points=points,
        distance_m=raw["summary"]["lengthInMeters"],
        duration_s=raw["summary"]["travelTimeInSeconds"],
        timing=timing,
    )


class TomTomClient:
    def __init__(self, api_key: str, transport: httpx.BaseTransport | None = None) -> None:
        self._api_key = api_key
        self._http = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT_SECONDS, transport=transport)

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        try:
            response = self._http.get(path, params={**params, "key": self._api_key})
        except httpx.HTTPError:
            raise ProviderError("The routing service could not be reached.") from None

        if response.status_code != 200:
            code = _error_code(response)
            if code in NO_ROUTE_CODES:
                raise NoRouteError("No truck route could be found between these locations.")
            logger.warning("TomTom returned HTTP %s (%s)", response.status_code, code)
            raise ProviderError("The routing service returned an error.")

        try:
            return response.json()
        except ValueError:
            raise ProviderError("The routing service returned an invalid response.") from None

    def calculate_routes(
        self,
        origin: LatLon,
        destination: LatLon,
        departure: datetime,
        load_lb: float,
        via: LatLon | None = None,
        max_alternatives: int = 0,
    ) -> list[Route]:
        stops = [origin, destination] if via is None else [origin, via, destination]
        locations = ":".join(_format_position(stop) for stop in stops)
        data = self._get(
            f"/routing/1/calculateRoute/{locations}/json",
            {
                "travelMode": "truck",
                "vehicleCommercial": "true",
                "vehicleWeight": gross_weight_kg(load_lb),
                "departAt": _format_departure(departure),
                "maxAlternatives": max_alternatives,
                "traffic": "true",
                "routeType": "fastest",
                "instructionsType": "coded",
                "routeRepresentation": "polyline",
            },
        )
        try:
            routes = [_parse_route(raw) for raw in data["routes"]]
        except (KeyError, TypeError, ValueError):
            raise ProviderError("The routing service returned an invalid response.") from None
        if not routes:
            raise NoRouteError("No truck route could be found between these locations.")
        return routes

    def geocode(self, query: str, limit: int = 5) -> list[Place]:
        data = self._get(
            f"/search/2/geocode/{quote(query, safe='')}.json",
            {"typeahead": "true", "limit": limit, "countrySet": GEOCODE_COUNTRIES},
        )
        places: dict[str, Place] = {}
        try:
            for result in data["results"]:
                label = result["address"]["freeformAddress"]
                position = LatLon(result["position"]["lat"], result["position"]["lon"])
                places.setdefault(label, Place(label=label, position=position))
        except (KeyError, TypeError):
            raise ProviderError("The routing service returned an invalid response.") from None
        return list(places.values())


@lru_cache(maxsize=1)
def get_tomtom_client() -> TomTomClient:
    if not settings.TOMTOM_API_KEY:
        raise ProviderError("The routing service is not configured.")
    return TomTomClient(settings.TOMTOM_API_KEY)
