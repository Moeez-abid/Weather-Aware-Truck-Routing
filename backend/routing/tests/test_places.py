from typing import Any

import httpx
import pytest

from routing.domain import LatLon, Place, ProviderError
from routing.places import (
    MAJOR_CITY_POPULATION,
    City,
    CitySearchError,
    OpenMeteoCitySearch,
    city_label,
    merge_results,
    search_places,
)

LAHORE = City("Lahore", "Punjab", "Pakistan", "PK", LatLon(31.558, 74.351), 13_004_135)
CHICAGO = City("Chicago", "Illinois", "United States", "US", LatLon(41.85, -87.65), 2_664_452)
TINY = City("Lahore", "Virginia", "United States", "US", LatLon(38.2, -77.98), 0)

NEIGHBORHOOD = Place("Islamabad Lahore, Punjab, Pakistan", LatLon(31.5, 74.3))
STREET = Place("Lahore Road, Tidworth, United Kingdom", LatLon(51.2, -1.66))
TOMTOM_CHICAGO = Place("Chicago, IL", LatLon(41.88, -87.63), is_city=True)
CHICAGO_ND = Place("Chicago, ND", LatLon(46.6, -99.0), is_city=True)


class FakeAddresses:
    def __init__(self, places: list[Place] | Exception) -> None:
        self.places = places
        self.calls = 0

    def geocode(self, query: str, limit: int = 5) -> list[Place]:
        self.calls += 1
        if isinstance(self.places, Exception):
            raise self.places
        return self.places


class FakeCities:
    def __init__(self, cities: list[City] | Exception) -> None:
        self.cities = cities
        self.calls = 0

    def search(self, query: str) -> list[City]:
        self.calls += 1
        if isinstance(self.cities, Exception):
            raise self.cities
        return self.cities


def labels(places: list[Place]) -> list[str]:
    return [place.label for place in places]


def test_a_major_city_missing_from_tomtom_comes_first() -> None:
    merged = merge_results([LAHORE, TINY], [NEIGHBORHOOD, STREET])

    assert labels(merged) == ["Lahore, Punjab, Pakistan", NEIGHBORHOOD.label, STREET.label]
    assert merged[0].position == LAHORE.position


def test_tomtoms_own_result_is_used_for_a_city_it_has() -> None:
    merged = merge_results([CHICAGO], [CHICAGO_ND, TOMTOM_CHICAGO])

    assert labels(merged) == ["Chicago, IL", "Chicago, ND"]


def test_only_a_tomtom_city_counts_as_the_same_place() -> None:
    street_in_lahore = Place("Mall Road, Lahore, Pakistan", LatLon(31.56, 74.35))

    merged = merge_results([LAHORE], [street_in_lahore])

    assert labels(merged) == ["Lahore, Punjab, Pakistan", street_in_lahore.label]


def test_small_places_keep_tomtoms_order() -> None:
    small = City("Smallville", "Kansas", "United States", "US", LatLon(39, -98), MAJOR_CITY_POPULATION - 1)

    assert labels(merge_results([small], [STREET])) == [STREET.label]


def test_at_most_two_cities_are_moved_up_and_five_results_returned() -> None:
    cities = [City(f"City {n}", "", "Pakistan", "PK", LatLon(n, n), 1_000_000) for n in range(4)]
    places = [Place(f"Street {n}", LatLon(50, n)) for n in range(5)]

    merged = merge_results(cities, places)

    assert labels(merged) == ["City 0, Pakistan", "City 1, Pakistan", "Street 0", "Street 1", "Street 2"]


def test_repeated_labels_are_dropped() -> None:
    twin = Place("Lahore, Punjab, Pakistan", LatLon(10, 10))

    assert labels(merge_results([LAHORE], [twin])) == ["Lahore, Punjab, Pakistan"]


@pytest.mark.parametrize(
    ("city", "label"),
    [
        (LAHORE, "Lahore, Punjab, Pakistan"),
        (CHICAGO, "Chicago, Illinois"),
        (City("Dubai", "Dubai", "United Arab Emirates", "AE", LatLon(25, 55), 1), "Dubai, United Arab Emirates"),
        (City("Monaco", "", "Monaco", "MC", LatLon(43.7, 7.4), 1), "Monaco, Monaco"),
    ],
)
def test_city_labels_follow_tomtoms_style(city: City, label: str) -> None:
    assert city_label(city) == label


def test_search_uses_both_services() -> None:
    assert labels(search_places("Lahore", FakeAddresses([STREET]), FakeCities([LAHORE]))) == [
        "Lahore, Punjab, Pakistan",
        STREET.label,
    ]


def test_city_search_failure_falls_back_to_tomtom() -> None:
    results = search_places("Lahore", FakeAddresses([STREET]), FakeCities(CitySearchError("down")))

    assert labels(results) == [STREET.label]


def test_tomtom_failure_falls_back_to_cities() -> None:
    results = search_places("Lahore", FakeAddresses(ProviderError("down")), FakeCities([LAHORE]))

    assert labels(results) == ["Lahore, Punjab, Pakistan"]


def test_tomtom_failure_without_cities_is_raised() -> None:
    with pytest.raises(ProviderError):
        search_places("Lahore", FakeAddresses(ProviderError("down")), FakeCities([]))


def test_a_repeated_search_is_answered_from_the_cache() -> None:
    addresses, cities = FakeAddresses([STREET]), FakeCities([LAHORE])

    first = search_places("Lahore", addresses, cities)
    again = search_places("LAHORE", addresses, cities)

    assert again == first
    assert (addresses.calls, cities.calls) == (1, 1)


def test_results_are_not_cached_when_city_search_failed() -> None:
    addresses, cities = FakeAddresses([STREET]), FakeCities(CitySearchError("down"))

    search_places("Lahore", addresses, cities)
    search_places("Lahore", addresses, cities)

    assert addresses.calls == 2


def city_search_returning(body: Any, status: int = 200, seen: list[httpx.Request] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=body)

    return OpenMeteoCitySearch(transport=httpx.MockTransport(handler))


def test_open_meteo_cities_are_parsed() -> None:
    seen: list[httpx.Request] = []
    body = {
        "results": [
            {
                "name": "Lahore",
                "latitude": 31.558,
                "longitude": 74.35071,
                "country_code": "PK",
                "country": "Pakistan",
                "admin1": "Punjab",
                "population": 13004135,
            },
            {"name": "Lahore", "latitude": 38.2, "longitude": -77.98, "country_code": "US"},
        ]
    }

    cities = city_search_returning(body, seen=seen).search("Lahore")

    assert cities[0] == City("Lahore", "Punjab", "Pakistan", "PK", LatLon(31.558, 74.35071), 13004135)
    assert cities[1].population == 0
    assert seen[0].url.params["name"] == "Lahore"
    assert seen[0].url.params["language"] == "en"


def test_no_matches_is_an_empty_list() -> None:
    assert city_search_returning({"generationtime_ms": 0.1}).search("Zzzz") == []


@pytest.mark.parametrize(("body", "status"), [({}, 500), ({"results": [{"name": "x"}]}, 200)])
def test_failures_raise_city_search_error(body: Any, status: int) -> None:
    with pytest.raises(CitySearchError):
        city_search_returning(body, status).search("Lahore")
