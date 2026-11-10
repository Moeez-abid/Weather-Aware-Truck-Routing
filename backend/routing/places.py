"""Address search: TomTom for addresses, with major cities from Open-Meteo listed first.

TomTom finds streets and addresses well, but it ranks some large cities badly outside North
America: "Lahore" returns a neighborhood and streets, but not the city of 13 million. Open-Meteo's
place search ranks places by population, so its largest matches go first. When TomTom also has
that city, TomTom's result and label are used, so US cities still read "Chicago, IL".
"""

import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

import httpx
from django.core.cache import cache

from routing.domain import LatLon, Place, RoutingError
from routing.geometry import haversine_m

logger = logging.getLogger(__name__)

CITY_SEARCH_URL = "https://geocoding-api.open-meteo.com/v1/search"
TIMEOUT_SECONDS = 10
RESULT_LIMIT = 5
# Smaller places are left to TomTom's own ranking.
MAJOR_CITY_POPULATION = 50_000
MAX_MAJOR_CITIES = 2
# A TomTom city this close to an Open-Meteo city is taken to be the same place.
SAME_CITY_METERS = 20_000
CACHE_SECONDS = 24 * 60 * 60


class CitySearchError(Exception):
    pass


@dataclass(frozen=True)
class City:
    name: str
    region: str
    country: str
    country_code: str
    position: LatLon
    population: int


class AddressSearch(Protocol):
    def geocode(self, query: str, limit: int = RESULT_LIMIT) -> list[Place]: ...


class CitySearch(Protocol):
    def search(self, query: str) -> list[City]: ...


def _parse_city(raw: dict[str, Any]) -> City:
    return City(
        name=raw["name"],
        region=raw.get("admin1") or "",
        country=raw.get("country") or "",
        country_code=raw.get("country_code") or "",
        position=LatLon(float(raw["latitude"]), float(raw["longitude"])),
        population=int(raw.get("population") or 0),
    )


class OpenMeteoCitySearch:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        # IPv4 only. This host also has an IPv6 address, and on networks where IPv6 is listed but
        # doesn't work, httpx waits for it to fail first, which added up to 20 seconds to a search.
        if transport is None:
            transport = httpx.HTTPTransport(local_address="0.0.0.0")
        self._http = httpx.Client(timeout=TIMEOUT_SECONDS, transport=transport)

    def search(self, query: str) -> list[City]:
        try:
            response = self._http.get(
                CITY_SEARCH_URL,
                params={"name": query, "count": RESULT_LIMIT, "language": "en", "format": "json"},
            )
            response.raise_for_status()
            return [_parse_city(raw) for raw in response.json().get("results", [])]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise CitySearchError(type(error).__name__) from None


@lru_cache(maxsize=1)
def get_city_search() -> OpenMeteoCitySearch:
    return OpenMeteoCitySearch()


def city_label(city: City) -> str:
    """Matches TomTom's style: the country is left out for US places."""
    parts = [city.name]
    if city.region and city.region != city.name:
        parts.append(city.region)
    if city.country and city.country_code != "US":
        parts.append(city.country)
    return ", ".join(parts)


def merge_results(cities: Sequence[City], places: Sequence[Place]) -> list[Place]:
    """Major cities first, then TomTom's results in its own order, without repeats."""
    used: set[int] = set()
    merged: list[Place] = []
    major = [city for city in cities if city.population >= MAJOR_CITY_POPULATION]
    for city in major[:MAX_MAJOR_CITIES]:
        match = next(
            (
                index
                for index, place in enumerate(places)
                if index not in used
                and place.is_city
                and haversine_m(place.position, city.position) <= SAME_CITY_METERS
            ),
            None,
        )
        if match is None:
            merged.append(Place(label=city_label(city), position=city.position, is_city=True))
        else:
            used.add(match)
            merged.append(places[match])
    merged.extend(place for index, place in enumerate(places) if index not in used)

    seen: set[str] = set()
    unique = []
    for place in merged:
        if place.label not in seen:
            seen.add(place.label)
            unique.append(place)
    return unique[:RESULT_LIMIT]


def search_places(query: str, addresses: AddressSearch, cities: CitySearch) -> list[Place]:
    """Search both services at once. Either one failing leaves the other's results."""
    key = f"places:{query.casefold()}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    with ThreadPoolExecutor(2) as pool:
        address_job = pool.submit(addresses.geocode, query, RESULT_LIMIT)
        city_job = pool.submit(cities.search, query)

    city_results: list[City] = []
    city_failed = False
    try:
        city_results = city_job.result()
    except CitySearchError as error:
        logger.warning("Open-Meteo city search failed: %s", error)
        city_failed = True

    try:
        address_results = address_job.result()
    except RoutingError:
        if city_failed or not city_results:
            raise
        return merge_results(city_results, [])

    results = merge_results(city_results, address_results)
    if not city_failed:
        # Saves both services' quotas when the same text is typed again.
        cache.set(key, results, CACHE_SECONDS)
    return results
